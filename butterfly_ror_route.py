#!/usr/bin/env python3
"""
Calculate switch states for ROR routing on the Butterfly topology used by
visual_benes.py.

ROR definition:
    output lane y receives data from input lane (y + offset) mod N.

Switch semantics:
    broadcast = 0
    state 0: input 0 -> output 0, input 1 -> output 1
    state 1: input 0 -> output 1, input 1 -> output 0

The internal Butterfly route for logical output lane y ends at internal final
lane bit_reverse(y). visual_benes.py connects that internal lane back to
external output lane y, so the visible output order is normal.

The output control bit string is stage-major, matching visual_benes.py:
stage 0 switch 0, stage 0 switch 1, ..., then stage 1, etc.
"""

import argparse
import json
import math
from typing import Dict, List, Optional, Tuple


Assignment = Tuple[int, int, int]
Conflict = Tuple[int, int, int, int, int, int]


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def inverse_perfect_shuffle(j: int, m: int) -> int:
    return (j >> 1) | ((j & 1) << (m - 1))


def bit_reverse(value: int, width: int) -> int:
    result = 0
    for _ in range(width):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def butterfly_wire_groups(n: int, stage: int) -> List[Tuple[int, int, int]]:
    """Return (lane_start, lane_count, log2(lane_count)) for a wire stage."""
    groups: List[Tuple[int, int, int]] = []

    def visit(size: int, stage_start: int, switch_start: int) -> None:
        if size == 2:
            return

        if stage_start == stage:
            groups.append((switch_start * 2, size, int(math.log2(size))))

        visit(size // 2, stage_start + 1, switch_start)
        visit(size // 2, stage_start + 1, switch_start + size // 4)

    visit(n, 0, 0)
    return groups


def next_stage_input_lane(n: int, stage: int, output_lane: int) -> int:
    """Follow one Butterfly wire from stage output to next-stage input."""
    for start, size, log_size in butterfly_wire_groups(n, stage):
        if start <= output_lane < start + size:
            return start + inverse_perfect_shuffle(output_lane - start, log_size)

    raise ValueError(f"lane {output_lane} is not in any wire group for stage {stage}")


def route_path(n: int, input_lane: int, output_lane: int) -> List[Assignment]:
    """Return the unique path's switch assignments for input_lane -> output_lane."""
    num_stages = int(math.log2(n))

    for path_bits in range(1 << num_stages):
        lane = input_lane
        assignments: List[Assignment] = []

        for stage in range(num_stages):
            state = (path_bits >> (num_stages - stage - 1)) & 1
            switch_idx = lane // 2
            input_port = lane & 1
            output_port = input_port ^ state
            stage_output_lane = switch_idx * 2 + output_port
            assignments.append((stage, switch_idx, state))

            if stage == num_stages - 1:
                lane = stage_output_lane
            else:
                lane = next_stage_input_lane(n, stage, stage_output_lane)

        if lane == output_lane:
            return assignments

    raise ValueError(f"no path from input {input_lane} to output {output_lane}")


def xor_tag_path(n: int, input_lane: int, logical_output_lane: int) -> List[Assignment]:
    """
    Return path assignments using XOR-tag routing.

    The internal Butterfly route for logical output y ends at bit_reverse(y),
    so stage s uses bit s of input_lane XOR logical_output_lane.
    """
    num_stages = int(math.log2(n))
    tag = input_lane ^ logical_output_lane
    internal_output_lane = bit_reverse(logical_output_lane, num_stages)
    lane = input_lane
    assignments: List[Assignment] = []

    for stage in range(num_stages):
        state = (tag >> stage) & 1
        switch_idx = lane // 2
        input_port = lane & 1
        output_port = input_port ^ state
        stage_output_lane = switch_idx * 2 + output_port
        assignments.append((stage, switch_idx, state))

        if stage == num_stages - 1:
            lane = stage_output_lane
        else:
            lane = next_stage_input_lane(n, stage, stage_output_lane)

    if lane != internal_output_lane:
        raise AssertionError(
            f"XOR-tag route ended at internal output {lane}, "
            f"expected {internal_output_lane}"
        )

    return assignments


def calculate_ror_route(
    n: int,
    offset: int,
) -> Tuple[Optional[List[List[int]]], Optional[Conflict]]:
    """
    Calculate Butterfly switch states for ROR.

    Returns:
        (states, None) if routable.
        (None, conflict) only if the topology invariants are broken.

    Conflict fields:
        stage, switch_idx, old_state, new_state, input_lane, logical_output_lane
    """
    if not is_power_of_two(n):
        raise ValueError("N must be a power of two")
    if n < 2:
        raise ValueError("N must be at least 2")

    offset %= n
    num_stages = int(math.log2(n))
    switches_per_stage = n // 2
    states: List[List[Optional[int]]] = [
        [None for _ in range(switches_per_stage)]
        for _ in range(num_stages)
    ]

    for logical_output_lane in range(n):
        input_lane = (logical_output_lane + offset) % n
        for stage, switch_idx, state in xor_tag_path(n, input_lane, logical_output_lane):
            current_state = states[stage][switch_idx]
            if current_state is not None and current_state != state:
                return None, (
                    stage,
                    switch_idx,
                    current_state,
                    state,
                    input_lane,
                    logical_output_lane,
                )
            states[stage][switch_idx] = state

    complete_states: List[List[int]] = [
        [0 if state is None else state for state in stage]
        for stage in states
    ]
    return complete_states, None


def control_bits(states: List[List[int]]) -> str:
    return "".join(str(state) for stage in states for state in stage)


def output_mapping(n: int, offset: int) -> List[Dict[str, int]]:
    offset %= n
    width = int(math.log2(n))
    return [
        {
            "output": output_lane,
            "internal_output": bit_reverse(output_lane, width),
            "input": (output_lane + offset) % n,
        }
        for output_lane in range(n)
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate Butterfly switch states for ROR routing."
    )
    parser.add_argument("N", type=int, help="network size, must be a power of two")
    parser.add_argument("offset", type=int, help="ROR offset")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    n = args.N
    offset = args.offset % n if n > 0 else args.offset

    states, conflict = calculate_ror_route(n, offset)

    if args.json:
        if states is None:
            stage, switch_idx, old_state, new_state, input_lane, output_lane = conflict
            print(json.dumps({
                "N": n,
                "offset": offset,
                "routable": False,
                "conflict": {
                    "stage": stage,
                    "switch": switch_idx,
                    "old_state": old_state,
                    "new_state": new_state,
                    "input": input_lane,
                    "output": output_lane,
                },
            }, indent=2))
            return 1

        print(json.dumps({
            "N": n,
            "offset": offset,
            "routable": True,
            "states": states,
            "control_bits": control_bits(states),
            "mapping": output_mapping(n, offset),
        }, indent=2))
        return 0

    print(f"N = {n}")
    print(f"offset = {offset}")
    print("semantics = broadcast 0")
    print("mapping = output lane y <- input lane (y + offset) mod N")
    print("internal final lane = bit_reverse(output lane)")

    if states is None:
        stage, switch_idx, old_state, new_state, input_lane, output_lane = conflict
        print("routable = no")
        print(
            "conflict = "
            f"stage {stage}, switch {switch_idx}: "
            f"already needs {old_state}, but output {output_lane} "
            f"from input {input_lane} needs {new_state}"
        )
        return 1

    print("routable = yes")
    print(f"control_bits = {control_bits(states)}")
    print("states:")
    for stage_idx, stage_states in enumerate(states):
        row = " ".join(str(state) for state in stage_states)
        print(f"  stage {stage_idx}: {row}")
    print("mapping:")
    for item in output_mapping(n, offset):
        print(
            f"  out {item['output']:02d} "
            f"(internal {item['internal_output']:02d}) <- "
            f"in {item['input']:02d}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
