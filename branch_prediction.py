import m5
from m5.objects import *
import os
import argparse

parser = argparse.ArgumentParser(description='Branch Prediction Analysis in gem5')
parser.add_argument('--bp_type', type=str, default='tournament',
                    choices=['none', 'static', 'tournament', 'bimode'],
                    help='Branch predictor type')
parser.add_argument('--local_pred_size', type=int, default=2048,
                    help='Size of local predictor')
parser.add_argument('--local_ctr_bits', type=int, default=2,
                    help='Bits per counter in local predictor')
parser.add_argument('--global_pred_size', type=int, default=8192,
                    help='Size of global predictor')
parser.add_argument('--global_ctr_bits', type=int, default=2,
                    help='Bits per counter in global predictor')
parser.add_argument('--choice_pred_size', type=int, default=8192,
                    help='Size of choice predictor')
parser.add_argument('--choice_ctr_bits', type=int, default=2,
                    help='Bits per counter in choice predictor')
parser.add_argument('--btb_entries', type=int, default=4096,
                    help='Number of BTB entries')
parser.add_argument('--ras_size', type=int, default=16,
                    help='Return address stack size')

args = parser.parse_args()

def create_system(bp_type='tournament'):
    """Create a system with the specified branch predictor type."""
    system = System()

    # Set up clock domain
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = '1GHz'
    system.clk_domain.voltage_domain = VoltageDomain()

    # Set up memory mode
    system.mem_mode = 'timing'
    system.mem_ranges = [AddrRange('512MB')]

    # Create memory bus
    system.membus = SystemXBar()

    # Create CPU
    system.cpu = X86MinorCPU()

    # Configure branch predictor
    if bp_type == 'none':
        system.cpu.branchPred = NULL
    elif bp_type == 'static':
        system.cpu.branchPred = StaticBP()
    elif bp_type == 'tournament':
        system.cpu.branchPred = TournamentBP(
            localPredictorSize=args.local_pred_size,
            localCtrBits=args.local_ctr_bits,
            globalPredictorSize=args.global_pred_size,
            globalCtrBits=args.global_ctr_bits,
            choicePredictorSize=args.choice_pred_size,
            choiceCtrBits=args.choice_ctr_bits,
            BTBEntries=args.btb_entries,
            RASSize=args.ras_size,
        )
    elif bp_type == 'bimode':
        system.cpu.branchPred = BiModeBP(
            globalPredictorSize=args.global_pred_size,
            globalCtrBits=args.global_ctr_bits,
            choicePredictorSize=args.choice_pred_size,
            choiceCtrBits=args.choice_ctr_bits,
            BTBEntries=args.btb_entries,
            RASSize=args.ras_size,
        )

    # Configure MinorCPU pipeline stages
    system.cpu.fetch1LineSnapWidth = 64
    system.cpu.fetch1FetchLimit = 1
    system.cpu.fetch1ToFetch2ForwardDelay = 1
    system.cpu.fetch2InputBufferSize = 2
    system.cpu.fetch2ToDecodeForwardDelay = 1
    system.cpu.decodeInputBufferSize = 3
    system.cpu.decodeToExecuteForwardDelay = 1
    system.cpu.executeInputBufferSize = 7
    system.cpu.executeMaxAccessesInMemory = 2
    system.cpu.executeCommitLimit = 2
    system.cpu.executeMemoryCommitLimit = 1
    system.cpu.executeIssueLimit = 2
    system.cpu.executeLSQRequestsQueueSize = 1
    system.cpu.executeLSQTransfersQueueSize = 2
    system.cpu.executeMemoryWidth = 0

    # Create and connect interrupt controller
    system.cpu.createInterruptController()

    # Create L1 caches
    system.l1i = Cache(size='32kB',
                      assoc=8,
                      tag_latency=1,
                      data_latency=1,
                      response_latency=1,
                      mshrs=4,
                      tgts_per_mshr=20)

    system.l1d = Cache(size='32kB',
                      assoc=8,
                      tag_latency=1,
                      data_latency=1,
                      response_latency=1,
                      mshrs=4,
                      tgts_per_mshr=20)

    # Connect CPU to L1 caches
    system.l1i.cpu_side = system.cpu.icache_port
    system.l1d.cpu_side = system.cpu.dcache_port

    # Connect L1 caches to memory bus
    system.l1i.mem_side = system.membus.cpu_side_ports
    system.l1d.mem_side = system.membus.cpu_side_ports

    # Create memory controller
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports

    # Connect system port
    system.system_port = system.membus.cpu_side_ports

    return system

# Create the test process
def create_process(binary_path):
    process = Process()
    process.cmd = [binary_path]
    process.executable = binary_path
    process.cwd = os.getcwd()
    return process

# Create the system with the configured branch predictor
print(f"Creating system with branch predictor: {args.bp_type}")
system = create_system(args.bp_type)

# Set up SE mode workload
binary = os.path.join(os.getcwd(), 'tests/test-progs/hello/bin/x86/linux/hello')
process = create_process(binary)

# Set up system workload
system.workload = SEWorkload.init_compatible(binary)

# Set CPU workload
system.cpu.workload = process
system.cpu.createThreads()

# Create root
root = Root(full_system=False, system=system)

# Instantiate simulation
m5.instantiate()

# Run simulation
print(f"Beginning simulation with {args.bp_type} branch predictor...")
start_tick = m5.curTick()
exit_event = m5.simulate()
end_tick = m5.curTick()

print("\nSimulation completed!")
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")

# Dump statistics
m5.stats.dump()

# Calculate and print key metrics
cycles = (end_tick - start_tick) / 1000
print(f"Branch predictor type: {args.bp_type}")
print(f"Simulation ticks: {end_tick - start_tick}")
print(f"CPU cycles: {cycles}")

# Try to read instructions executed and calculate IPC/CPI
try:
    # Attempt to print stats directly
    print("\nBranch prediction stats:")
    
    # Branch mispredictions
    if args.bp_type != 'none':
        mispredicts = system.cpu.branchPred.lookupIncorrect if hasattr(system.cpu.branchPred, 'lookupIncorrect') else 0
        correct_predictions = system.cpu.branchPred.lookupCorrect if hasattr(system.cpu.branchPred, 'lookupCorrect') else 0
        total_predictions = mispredicts + correct_predictions if correct_predictions > 0 else 1
        accuracy = (correct_predictions / total_predictions) * 100 if total_predictions > 0 else 0
        
        print(f"Branch predictions: {total_predictions}")
        print(f"Correct predictions: {correct_predictions}")
        print(f"Mispredictions: {mispredicts}")
        print(f"Prediction accuracy: {accuracy:.2f}%")
    
    # Instructions and IPC/CPI calculations
    instructions = system.cpu.numInsts if hasattr(system.cpu, 'numInsts') else None
    if instructions is None:
        instructions = system.cpu.committedInsts if hasattr(system.cpu, 'committedInsts') else 0
    
    if instructions > 0:
        ipc = float(instructions) / cycles
        cpi = cycles / float(instructions)
        print(f"\nTotal Instructions: {instructions}")
        print(f"Instructions per Cycle (IPC): {ipc:.4f}")
        print(f"Cycles per Instruction (CPI): {cpi:.4f}")
    else:
        print("\nCouldn't determine instruction count directly.")
        print("Check the stats.txt file for detailed statistics.")

except Exception as e:
    print(f"Error accessing statistics: {e}")
    print("Check the stats.txt file for detailed statistics.")

print("\nStats file has been written to m5out/stats.txt")
