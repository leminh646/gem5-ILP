#!/usr/bin/env python3

import m5
from m5.objects import *
import argparse
import os
import sys
import time

def create_superscalar_cpu(width=2, bp_type='TournamentBP'):
    """Create a MinorCPU with superscalar configuration"""
    cpu = MinorCPU()
    
    # Configure pipeline stages for superscalar operation
    cpu.fetch1LineSnapWidth = 0  # Ensure clean stage boundaries
    cpu.fetch1ToFetch2ForwardDelay = 1  # Stage delay between fetch stages
    cpu.fetch2ToDecodeForwardDelay = 1  # Delay between fetch and decode
    cpu.decodeToExecuteForwardDelay = 1  # Delay between decode and execute
    cpu.executeToMemoryForwardDelay = 1  # Delay between execute and memory
    cpu.memoryToWritebackForwardDelay = 1  # Delay between memory and writeback

    # Configure execution stage for superscalar operation
    cpu.executeAllowEarlyMemoryIssue = True  # Allow memory operations to issue early
    cpu.executeBranchDelay = 1  # Branch resolution delay
    cpu.executeCommitLimit = width  # Number of instructions that can be committed per cycle
    cpu.executeMemoryCommitLimit = width  # Memory instructions per cycle
    cpu.executeInputBufferSize = width * 4  # Size of input buffer to execute stage
    cpu.executeIssueLimit = width  # Instructions issued per cycle
    cpu.executeLSQMaxStoreBufferStoresPerCycle = width  # Store buffer bandwidth
    cpu.executeLSQRequestsQueueSize = width * 2  # LSQ size
    cpu.executeLSQStoreBufferSize = width * 4  # Store buffer size
    cpu.executeLSQTransfersQueueSize = width * 2  # LSQ transfer queue size
    cpu.executeMaxAccessesInMemory = width * 2  # Maximum number of concurrent memory accesses
    cpu.executeMemoryWidth = width  # Memory operation width
    cpu.executeSetTraceTimeOnCommit = True  # Set instruction trace times on commit

    # Pipeline widths for superscalar operation
    cpu.decodeInputWidth = width  # Instructions per cycle at decode input
    cpu.decodeToExecuteForwardWidth = width  # Width between decode and execute
    cpu.executeInputWidth = width  # Instructions per cycle at execute input
    cpu.executeCycleInput = True  # Enable cycle-by-cycle input to execute
    cpu.fetch1LineWidth = width  # Instruction fetch width
    cpu.fetch1ToFetch2ForwardWidth = width  # Width between fetch stages
    cpu.fetch2InputBufferSize = width * 2  # Size of fetch2 input buffer
    cpu.fetch2ToDecodeForwardWidth = width  # Width between fetch2 and decode
    
    # Configure branch predictor
    if bp_type == 'StaticBP':
        cpu.branchPred = StaticBP()
    elif bp_type == 'LocalBP':
        cpu.branchPred = LocalBP(
            localPredictorSize=2048,
            localCtrBits=2
        )
    elif bp_type == 'TournamentBP':
        cpu.branchPred = TournamentBP(
            localPredictorSize=2048,
            localCtrBits=2,
            globalPredictorSize=8192,
            globalCtrBits=2,
            choicePredictorSize=8192,
            choiceCtrBits=2
        )
    elif bp_type == 'BiModeBP':
        cpu.branchPred = BiModeBP(
            globalPredictorSize=8192,
            choicePredictorSize=8192,
            choiceCtrBits=2
        )
    
    return cpu

def main():
    parser = argparse.ArgumentParser(description='Superscalar Pipeline Test')
    parser.add_argument('--width', type=int, default=2, 
                        help='Width of the pipeline (instructions per stage)')
    parser.add_argument('--bp-type', type=str, default='TournamentBP',
                        choices=['StaticBP', 'LocalBP', 'TournamentBP', 'BiModeBP'],
                        help='Branch predictor type')
    args = parser.parse_args()
    
    # Create the system
    system = System()
    
    # Set up clock domain
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = '2GHz'
    system.clk_domain.voltage_domain = VoltageDomain()
    
    # Set up memory mode
    system.mem_mode = 'timing'
    system.mem_ranges = [AddrRange('512MB')]
    
    # Create a memory bus
    system.membus = SystemXBar()
    
    # Create CPU - using our superscalar configuration
    system.cpu = create_superscalar_cpu(width=args.width, bp_type=args.bp_type)
    
    # Create and connect interrupt controller
    system.cpu.createInterruptController()
    
    # Create L1 caches
    system.l1i = Cache(size='32kB',
                     assoc=2,
                     tag_latency=1,
                     data_latency=1,
                     response_latency=1,
                     mshrs=4,
                     tgts_per_mshr=20)
    
    system.l1d = Cache(size='32kB',
                     assoc=2,
                     tag_latency=1,
                     data_latency=1,
                     response_latency=1,
                     mshrs=4,
                     tgts_per_mshr=20)
    
    # Create a crossbar to connect L1 caches to L2 cache
    system.tol2bus = L2XBar()
    
    # Create L2 cache
    system.l2 = Cache(size='256kB',
                     assoc=8,
                     tag_latency=2,
                     data_latency=2,
                     response_latency=2,
                     mshrs=16,
                     tgts_per_mshr=20)
    
    # Connect CPU to L1 caches
    system.l1i.cpu_side = system.cpu.icache_port
    system.l1d.cpu_side = system.cpu.dcache_port
    
    # Connect L1 caches to L2 crossbar
    system.l1i.mem_side = system.tol2bus.cpu_side_ports
    system.l1d.mem_side = system.tol2bus.cpu_side_ports
    
    # Connect L2 crossbar to L2 cache
    system.l2.cpu_side = system.tol2bus.mem_side_ports
    
    # Connect L2 cache to memory bus
    system.l2.mem_side = system.membus.cpu_side_ports
    
    # Create memory controller
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports
    
    # Connect system port
    system.system_port = system.membus.cpu_side_ports
    
    # Create process
    process = Process()
    process.cmd = ['tests/branch_test']
    system.cpu.workload = process
    system.cpu.createThreads()
    
    # Create root
    root = Root(full_system=False, system=system)
    
    # Print configuration details
    print(f"\n===== SUPERSCALAR PIPELINE CONFIGURATION =====")
    print(f"Pipeline Width: {args.width}")
    print(f"Branch Predictor: {args.bp_type}")
    print("===========================================\n")
    
    # Instantiate simulation
    m5.instantiate()
    
    # Run simulation
    print("Starting simulation...")
    start_time = time.time()
    exit_event = m5.simulate()
    end_time = time.time()
    sim_seconds = m5.curTick() / 1e12  # Convert ticks to seconds
    wall_seconds = end_time - start_time
    print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
    print(f"Simulation took {wall_seconds:.2f} seconds of wall clock time")
    
    # Dump statistics
    print("\nDumping statistics...")
    m5.stats.dump()
    
    # Print performance statistics
    print("\n===== PERFORMANCE STATISTICS =====")
    
    # Get CPU stats
    try:
        cycles = system.cpu.numCycles
        print(f"Cycles: {cycles}")
    except AttributeError:
        print("Could not access numCycles")
        cycles = 0
        
    try:
        instructions = system.cpu.committedInsts
        print(f"Instructions (committedInsts): {instructions}")
    except AttributeError:
        try:
            instructions = system.cpu.numInsts
            print(f"Instructions (numInsts): {instructions}")
        except AttributeError:
            print("Could not access instruction count")
            instructions = 0
    
    # Calculate IPC and CPI
    if cycles > 0 and instructions > 0:
        ipc = instructions / cycles
        cpi = cycles / instructions
        print(f"IPC (Instructions Per Cycle): {ipc:.4f}")
        print(f"CPI (Cycles Per Instruction): {cpi:.4f}")
    else:
        print("Cannot calculate IPC/CPI: cycles or instructions is zero")
    
    # Branch prediction stats
    if hasattr(system.cpu, 'branchPred'):
        try:
            lookups = system.cpu.branchPred.lookups
            incorrect = system.cpu.branchPred.incorrect
            correct = lookups - incorrect
            accuracy = (correct / lookups) * 100 if lookups > 0 else 0
            
            print("\n===== BRANCH PREDICTION STATISTICS =====")
            print(f"Branch Predictor Type: {args.bp_type}")
            print(f"Total Branch Predictions: {lookups}")
            print(f"Correct Predictions: {correct}")
            print(f"Incorrect Predictions: {incorrect}")
            print(f"Prediction Accuracy: {accuracy:.2f}%")
        except AttributeError as e:
            print(f"Error accessing branch predictor statistics: {e}")
    
    # Print pipeline configuration
    print("\n===== PIPELINE CONFIGURATION =====")
    print(f"Pipeline Width: {args.width}")
    for attr in dir(system.cpu):
        if attr.startswith('execute') or attr.startswith('decode') or attr.startswith('fetch'):
            try:
                value = getattr(system.cpu, attr)
                if isinstance(value, (int, float, bool)):
                    print(f"{attr}: {value}")
            except:
                pass

if __name__ == "__main__":
    main()
