#!/usr/bin/env python3
import argparse

def parse_pipeline_trace(trace_file):
    stages = {
        'Fetch1': [],
        'Fetch2': [],
        'Execute': [],
        'Memory': [],
        'Commit': []
    }
    
    with open(trace_file, 'r') as f:
        for line in f:
            if 'activity=' in line and 'stages=' in line:
                # Extract cycle number
                cycle = int(line.split(':')[0].strip())
                
                # Extract stage information
                stage_info = line.split('stages=')[1].strip()
                stage_states = stage_info.split(',')
                
                if len(stage_states) >= 5:  # Make sure we have all stages
                    stages['Fetch1'].append((cycle, stage_states[0]))
                    stages['Fetch2'].append((cycle, stage_states[1]))
                    stages['Execute'].append((cycle, stage_states[2]))
                    stages['Memory'].append((cycle, stage_states[3]))
                    stages['Commit'].append((cycle, stage_states[4]))
                    
    return stages

def find_active_cycles(stages):
    """Find cycles where there is activity in any stage."""
    active_cycles = set()
    for stage_data in stages.values():
        for cycle, state in stage_data:
            if state != 'E' and state != '-':
                active_cycles.add(cycle)
    return sorted(list(active_cycles))

def print_pipeline_visualization(stages, start_cycle, num_cycles=20):
    print("\nPipeline Visualization:")
    print("Cycle   | F1  | F2  | EX  | MEM | COM")
    print("---------------------------------------")
    
    for i in range(start_cycle, start_cycle + num_cycles):
        cycle_info = [str(i).rjust(7)]
        
        for stage in ['Fetch1', 'Fetch2', 'Execute', 'Memory', 'Commit']:
            state = '  -  '
            for cycle, s in stages[stage]:
                if cycle == i:
                    state = f' {s:^3} '
                    break
            cycle_info.append(state)
            
        print(" | ".join(cycle_info))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Visualize gem5 pipeline trace')
    parser.add_argument('trace_file', help='Path to the trace file')
    parser.add_argument('--start', type=int, help='Starting cycle')
    parser.add_argument('--cycles', type=int, default=20, help='Number of cycles to show')
    parser.add_argument('--show-active', action='store_true', help='Show only cycles with activity')
    
    args = parser.parse_args()
    stages = parse_pipeline_trace(args.trace_file)
    
    if args.show_active:
        active_cycles = find_active_cycles(stages)
        if active_cycles:
            print(f"\nFound activity at cycles: {active_cycles[:10]}")
            if not args.start:
                args.start = active_cycles[0]
    
    start_cycle = args.start if args.start is not None else 500
    print_pipeline_visualization(stages, start_cycle, args.cycles)
