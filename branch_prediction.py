import argparse
import sys
import os

# Add gem5 Python library path
gem5_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build', 'x86')
sys.path.append(gem5_path)

import m5
from m5.objects import *

def parse_arguments():
    parser = argparse.ArgumentParser(description='gem5 Branch Prediction Simulation')
    
    # Branch predictor configuration arguments
    parser.add_argument('--bp-type', type=str, default='tournament', 
                        choices=['none', 'static', 'tournament', 'bimode'],
                        help='Type of branch predictor to use')
    
    # Benchmark configuration
    parser.add_argument('--cmd', type=str, default='./tests/simple_ilp',
                        help='Path to the benchmark executable')
    parser.add_argument('--options', type=str, default='branch 10000',
                        help='Options to pass to the benchmark')
    
    return parser.parse_args()

def create_system(args):
    # Create the system
    system = System()
    
    # Set up the clock
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = '1GHz'
    system.clk_domain.voltage_domain = VoltageDomain()
    
    # Memory
    system.mem_mode = 'timing'
    system.mem_ranges = [AddrRange('512MB')]
    
    # Create memory bus
    system.membus = SystemXBar()
    
    # Create CPU
    system.cpu = DerivO3CPU()
    
    # Configure branch predictor
    if args.bp_type == 'none':
        # Disable branch prediction
        system.cpu.branchPred = NULL
    elif args.bp_type == 'static':
        # Use a simple static predictor
        system.cpu.branchPred = StaticBP()
    elif args.bp_type == 'tournament':
        # Use a tournament predictor with detailed configuration
        system.cpu.branchPred = TournamentBP(
            localPredictorSize=2048,
            localCtrBits=2,
            globalPredictorSize=2048,
            globalCtrBits=2,
            choicePredictorSize=2048,
            choiceCtrBits=2
        )
    elif args.bp_type == 'bimode':
        # Use a bimode predictor
        system.cpu.branchPred = BiModeBP(
            globalPredictorSize=2048,
            globalCtrBits=2,
            choicePredictorSize=2048,
            choiceCtrBits=2
        )
    
    # Connect CPU ports
    system.cpu.icache_port = system.membus.cpu_side_ports
    system.cpu.dcache_port = system.membus.cpu_side_ports
    
    # Create memory controller
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports
    
    # Set up the process
    process = Process()
    process.executable = args.cmd
    process.cmd = [process.executable] + args.options.split()
    system.cpu.workload = process
    
    # Create the root
    root = Root(full_system = False, system = system)
    
    return system, root

def main():
    # Parse arguments
    args = parse_arguments()
    
    # Create the system
    system, root = create_system(args)
    
    # Instantiate the system
    m5.instantiate()
    
    # Simulate
    print(f"\n=== Running simulation with {args.bp_type} branch predictor ===")
    exit_event = m5.simulate()
    
    # Print simulation results
    try:
        # Collect branch prediction statistics
        branch_pred = system.cpu.branchPred
        
        # Attempt to get branch prediction metrics
        branch_metrics = {
            'lookups': 0,
            'mispredicts': 0,
            'accuracy': 0.0
        }
        
        # Metric names to try
        lookup_attrs = [
            'numBranches', 'numLookups', 'total_lookups', 
            'branches_processed', 'num_branches'
        ]
        mispredict_attrs = [
            'numMispred', 'mispredicted', 'num_mispredicted', 
            'mispredictions', 'num_mispredictions'
        ]
        
        # Find branch lookups
        for attr in lookup_attrs:
            if hasattr(branch_pred, attr):
                branch_metrics['lookups'] = getattr(branch_pred, attr)
                break
        
        # Find branch mispredictions
        for attr in mispredict_attrs:
            if hasattr(branch_pred, attr):
                branch_metrics['mispredicts'] = getattr(branch_pred, attr)
                break
        
        # Calculate accuracy
        if branch_metrics['lookups'] > 0:
            branch_metrics['accuracy'] = (1 - branch_metrics['mispredicts'] / branch_metrics['lookups']) * 100
        
        # Instructions and IPC/CPI calculations
        instructions = system.cpu.numInsts if hasattr(system.cpu, 'numInsts') else None
        if instructions is None:
            instructions = system.cpu.committedInsts if hasattr(system.cpu, 'committedInsts') else 0
        
        # Calculate cycles
        cycles = system.cpu.numCycles if hasattr(system.cpu, 'numCycles') else 0
        
        # Calculate performance metrics
        ipc = float(instructions) / cycles if cycles > 0 else 0
        cpi = cycles / float(instructions) if instructions > 0 else 0
        
        # Prepare results directory
        results_dir = 'branch_prediction_results'
        os.makedirs(results_dir, exist_ok=True)
        
        # Generate report
        report_file = os.path.join(results_dir, 'branch_prediction_report.txt')
        with open(report_file, 'w') as f:
            f.write("===== BRANCH PREDICTION PERFORMANCE ANALYSIS =====\n\n")
            f.write("SUMMARY OF RESULTS:\n")
            f.write(f"{'Predictor Type':<15} {'Cycles':<10} {'Instructions':<15} {'IPC':<8} {'CPI':<8} ")
            f.write(f"{'Branch Acc.%':<12} {'Branch Pred.':<15} {'Branch Mispr.'}\n")
            f.write("-" * 100 + "\n")
            
            f.write(f"{args.bp_type:<15} {cycles:<10} {instructions:<15} ")
            f.write(f"{ipc:<8.4f} {cpi:<8.4f} ")
            f.write(f"{branch_metrics['accuracy']:<12.2f} {branch_metrics['lookups']:<15} {branch_metrics['mispredicts']}\n")
        
        # Print results
        print(f"\nBranch Predictor: {args.bp_type}")
        print(f"Total Branch Lookups: {branch_metrics['lookups']}")
        print(f"Branch Mispredictions: {branch_metrics['mispredicts']}")
        print(f"Branch Prediction Accuracy: {branch_metrics['accuracy']:.2f}%")
        print(f"\nTotal Instructions: {instructions}")
        print(f"Instructions per Cycle (IPC): {ipc:.4f}")
        print(f"Cycles per Instruction (CPI): {cpi:.4f}")
        
        print(f"\nDetailed report saved to {report_file}")

    except Exception as e:
        print(f"Error accessing statistics: {e}")
        print("Check the stats.txt file for detailed statistics.")

if __name__ == '__main__':
    main()
