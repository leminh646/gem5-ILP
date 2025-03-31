#!/usr/bin/env python3

import m5
from m5.objects import *
import argparse
import os
import sys

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Simple SMT Test')
parser.add_argument('--width', type=int, default=4, 
                    help='Width of the pipeline (instructions per stage)')
parser.add_argument('--threads', type=int, default=2,
                    help='Number of hardware threads (SMT)')
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

# Create CPU with SMT capabilities
system.cpu = DerivO3CPU()
system.cpu.numThreads = args.threads

# Configure superscalar width parameters
system.cpu.fetchWidth = args.width
system.cpu.decodeWidth = args.width
system.cpu.renameWidth = args.width
system.cpu.dispatchWidth = args.width
system.cpu.issueWidth = args.width
system.cpu.wbWidth = args.width
system.cpu.commitWidth = args.width

# Set reasonable queue sizes based on width
system.cpu.numROBEntries = args.width * 32
system.cpu.LQEntries = args.width * 16
system.cpu.SQEntries = args.width * 16
system.cpu.numIQEntries = args.width * 16

# Configure branch predictor
if args.bp_type == 'TournamentBP':
    system.cpu.branchPred = TournamentBP(
        localPredictorSize=2048,
        localCtrBits=2,
        globalPredictorSize=8192,
        globalCtrBits=2,
        choicePredictorSize=8192,
        choiceCtrBits=2
    )

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

# Create processes for each thread
system.cpu.workload = []
for i in range(args.threads):
    process = Process()
    # Use the hello program that exists in the gem5 environment
    executable_path = os.path.join(os.getcwd(), 'tests/test-progs/hello/bin/x86/linux/hello')
    process.cmd = [executable_path]
    # Ensure each thread has its own executable path to fix the ISA issue
    process.executable = executable_path
    system.cpu.workload.append(process)

# Create threads after all workloads are added
system.cpu.createThreads()

# Create root
root = Root(full_system=False, system=system)

# Print configuration details
print(f"\n===== SMT PIPELINE CONFIGURATION =====")
print(f"Pipeline Width: {args.width}")
print(f"Hardware Threads: {args.threads}")
print(f"Branch Predictor: {args.bp_type}")
print("===========================================\n")

# Instantiate simulation
m5.instantiate()

# Run simulation
print("Starting simulation...")
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")

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
    
# Per-thread statistics
total_instructions = 0
for i in range(args.threads):
    try:
        thread_insts = system.cpu.committedInsts[i]
        print(f"Thread {i} Instructions: {thread_insts}")
        total_instructions += thread_insts
    except (AttributeError, IndexError):
        print(f"Could not access instructions for thread {i}")

print(f"Total Instructions: {total_instructions}")

# Calculate IPC and CPI
if cycles > 0 and total_instructions > 0:
    ipc = total_instructions / cycles
    cpi = cycles / total_instructions
    print(f"Overall IPC (Instructions Per Cycle): {ipc:.4f}")
    print(f"Overall CPI (Cycles Per Instruction): {cpi:.4f}")
else:
    print("Cannot calculate IPC/CPI: cycles or instructions is zero")

# Resource utilization
print("\n===== RESOURCE UTILIZATION =====")
try:
    # ROB utilization
    try:
        rob_util = system.cpu.rob.rob_utilization
        print(f"ROB Utilization: {rob_util:.2f}%")
    except AttributeError:
        print("Could not access ROB utilization")
    
    # Issue queue utilization
    try:
        iq_util = system.cpu.iq.iq_utilization
        print(f"Issue Queue Utilization: {iq_util:.2f}%")
    except AttributeError:
        print("Could not access issue queue utilization")
    
    # Load/Store queue utilization
    try:
        lq_util = system.cpu.lsq.lq_utilization
        sq_util = system.cpu.lsq.sq_utilization
        print(f"Load Queue Utilization: {lq_util:.2f}%")
        print(f"Store Queue Utilization: {sq_util:.2f}%")
    except AttributeError:
        print("Could not access LQ/SQ utilization")

except Exception as e:
    print(f"Error accessing resource utilization statistics: {e}")
