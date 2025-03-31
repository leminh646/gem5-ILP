import m5
from m5.objects import *
import os
import sys
import subprocess
import argparse
import traceback
import logging

# Add extensive logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename='superscalar_debug.log')

def log_exception(e):
    """Log exception with full traceback"""
    logging.error(f"Exception occurred: {e}")
    logging.error(traceback.format_exc())
    print(f"CRITICAL ERROR: {e}")
    traceback.print_exc()

try:
    parser = argparse.ArgumentParser(description='Superscalar Pipeline Configuration with O3CPU')
    parser.add_argument('--issue-width', type=int, default=2, 
                        help='Number of instructions that can be issued per cycle')
    parser.add_argument('--decode-width', type=int, default=2,
                        help='Number of instructions that can be decoded per cycle')
    parser.add_argument('--execute-width', type=int, default=2,
                        help='Number of instructions that can be executed per cycle')
    parser.add_argument('--commit-width', type=int, default=2,
                        help='Number of instructions that can be committed per cycle')
    parser.add_argument('--benchmark', type=str, default='branch_patterns',
                        help='Benchmark program to run')
    parser.add_argument('--options', type=str, default='10000',
                        help='Command line options for the benchmark')
    parser.add_argument('--bp-type', type=str, default='TournamentBP', 
                        choices=['NoBP', 'StaticBP', 'BiModeBP', 'LocalBP', 'TournamentBP'],
                        help='Branch predictor type')
    parser.add_argument('--debug', action='store_true',
                        help='Enable detailed debug output')

    args = parser.parse_args()

    # Create system
    system = System()

    # Set up clock domain
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = '2GHz'  # Faster clock for superscalar
    system.clk_domain.voltage_domain = VoltageDomain()

    # Set up memory mode
    system.mem_mode = 'timing'
    system.mem_ranges = [AddrRange('512MB')]

    # Create memory bus
    system.membus = SystemXBar()

    # Create CPU - using O3CPU for superscalar and out-of-order execution
    system.cpu = DerivO3CPU()

    # Configure the O3CPU for different issue widths
    system.cpu.fetchWidth = args.decode_width
    system.cpu.decodeWidth = args.decode_width
    system.cpu.renameWidth = args.decode_width
    system.cpu.dispatchWidth = args.issue_width
    system.cpu.issueWidth = args.issue_width
    system.cpu.wbWidth = args.execute_width
    system.cpu.commitWidth = args.commit_width

    # Configure execution units based on issue width
    # Always need at least one of each type
    system.cpu.fuPool = DefaultFUPool()

    # More execution units for wider issue widths
    if args.issue_width >= 2:
        # Add more integer ALUs
        system.cpu.fuPool.FUList[0].count = 2  # IntALU
        
    if args.issue_width >= 4:
        # Add even more execution units for quad issue
        system.cpu.fuPool.FUList[0].count = 4  # IntALU
        system.cpu.fuPool.FUList[1].count = 2  # IntMultDiv
        system.cpu.fuPool.FUList[2].count = 2  # FP ALU
        system.cpu.fuPool.FUList[3].count = 2  # FP MultDiv

    # Configure branch predictor with more detailed options
    def configure_branch_predictor(cpu, bp_type):
        """
        Configure branch predictor with different configurations
        """
        if bp_type == 'NoBP':
            cpu.branchPred = NULL
        elif bp_type == 'StaticBP':
            cpu.branchPred = StaticBP()
        elif bp_type == 'BiModeBP':
            cpu.branchPred = BiModeBP()
        elif bp_type == 'LocalBP':
            # Local history-based branch predictor
            cpu.branchPred = LocalBP()
        elif bp_type == 'TournamentBP':
            # Tournament branch predictor with multiple predictors
            tournament_bp = TournamentBP()
            
            # Global history predictor
            tournament_bp.globalPred = GlobalBP()
            tournament_bp.localPred = LocalBP()
            
            # Configure predictor parameters
            tournament_bp.globalPred.globalHistoryBits = 12
            tournament_bp.localPred.localHistoryBits = 10
            tournament_bp.localPred.localHistoryTableSize = 2048
            
            cpu.branchPred = tournament_bp
        else:
            # Default to Tournament BP with custom configuration
            tournament_bp = TournamentBP()
            tournament_bp.globalPred = GlobalBP()
            tournament_bp.localPred = LocalBP()
            cpu.branchPred = tournament_bp

    # Configure branch predictor
    configure_branch_predictor(system.cpu, args.bp_type)

    # Print branch predictor details
    print(f"\n===== BRANCH PREDICTOR CONFIGURATION =====")
    print(f"Branch Predictor Type: {args.bp_type}")
    if hasattr(system.cpu.branchPred, 'globalPred'):
        print("Global Predictor History Bits:", 
              getattr(system.cpu.branchPred.globalPred, 'globalHistoryBits', 'N/A'))
    if hasattr(system.cpu.branchPred, 'localPred'):
        print("Local Predictor History Bits:", 
              getattr(system.cpu.branchPred.localPred, 'localHistoryBits', 'N/A'))
        print("Local History Table Size:", 
              getattr(system.cpu.branchPred.localPred, 'localHistoryTableSize', 'N/A'))
    print("===========================================\n")

    # Enable debug flags if requested
    if args.debug:
        m5.util.addToPath('../')
        from common import Options
        from common import Simulation
        from common import ObjectList
        
        # Enable relevant debug flags
        m5.debug.flags["O3PipeView"] = True
        m5.debug.flags["Fetch"] = True
        m5.debug.flags["Decode"] = True
        m5.debug.flags["Rename"] = True
        m5.debug.flags["Issue"] = True
        m5.debug.flags["Commit"] = True

    def compile_benchmark(benchmark_path):
        """
        Compile the benchmark C file into an executable
        """
        # Construct source and executable paths
        source_path = benchmark_path + '.c'
        
        # Check if source file exists
        if not os.path.exists(source_path):
            print(f"Error: Benchmark source file not found: {source_path}")
            sys.exit(1)
        
        # Compile command
        compile_cmd = ['gcc', '-O3', '-o', benchmark_path, source_path]
        
        try:
            # Run compilation
            result = subprocess.run(compile_cmd, capture_output=True, text=True)
            
            # Check compilation result
            if result.returncode != 0:
                print("Compilation Error:")
                print(result.stderr)
                sys.exit(1)
            
            print(f"Successfully compiled {source_path}")
            return True
        
        except Exception as e:
            print(f"Error compiling benchmark: {e}")
            sys.exit(1)

    # Debug output to verify configuration
    print("\n===== SUPERSCALAR CONFIGURATION DETAILS (O3CPU) =====")
    print(f"Fetch Width: {system.cpu.fetchWidth}")
    print(f"Decode Width: {system.cpu.decodeWidth}")
    print(f"Rename Width: {system.cpu.renameWidth}")
    print(f"Dispatch Width: {system.cpu.dispatchWidth}")
    print(f"Issue Width: {system.cpu.issueWidth}")
    print(f"Writeback Width: {system.cpu.wbWidth}")
    print(f"Commit Width: {system.cpu.commitWidth}")
    print(f"Branch Predictor: {args.bp_type}")
    print(f"Integer ALUs: {system.cpu.fuPool.FUList[0].count}")
    print(f"Integer MultDiv: {system.cpu.fuPool.FUList[1].count}")
    print(f"FP ALUs: {system.cpu.fuPool.FUList[2].count}")
    print(f"FP MultDiv: {system.cpu.fuPool.FUList[3].count}")
    print("================================================\n")

    # Create and connect interrupt controller
    system.cpu.createInterruptController()

    # Create L1 caches
    system.l1i = Cache(size='32kB',
                      assoc=8,
                      tag_latency=1,
                      data_latency=1,
                      response_latency=1,
                      mshrs=8,
                      tgts_per_mshr=20)

    system.l1d = Cache(size='32kB',
                      assoc=8,
                      tag_latency=1,
                      data_latency=1,
                      response_latency=1,
                      mshrs=8,
                      tgts_per_mshr=20)

    # Create L2 cache
    system.l2 = Cache(size='256kB',
                     assoc=16,
                     tag_latency=5,
                     data_latency=5,
                     response_latency=5,
                     mshrs=16,
                     tgts_per_mshr=20)

    # Connect CPU to L1 caches
    system.l1i.cpu_side = system.cpu.icache_port
    system.l1d.cpu_side = system.cpu.dcache_port

    # Connect L1 caches to L2 cache
    system.l1i.mem_side = system.l2.cpu_side_ports
    system.l1d.mem_side = system.l2.cpu_side_ports

    # Connect L2 cache to memory bus
    system.l2.mem_side = system.membus.cpu_side_ports

    # Create memory controller
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports

    # Connect system port
    system.system_port = system.membus.cpu_side_ports

    # Set up workload
    benchmark_path = os.path.join(os.getcwd(), 'tests', args.benchmark)

    # Compile the benchmark before running
    compile_benchmark(benchmark_path)

    print(f"Benchmark: {args.benchmark}")
    print(f"Benchmark Options: {args.options}")

    # Verify benchmark exists and is executable
    print(f"Full Benchmark Path: {benchmark_path}")
    print(f"Benchmark Executable Exists: {os.path.exists(benchmark_path)}")
    print(f"Benchmark Executable is Executable: {os.access(benchmark_path, os.X_OK)}")

    # If not executable, try to make it executable
    if not os.access(benchmark_path, os.X_OK):
        try:
            os.chmod(benchmark_path, 0o755)
            print(f"Made {benchmark_path} executable")
        except Exception as e:
            print(f"Failed to make benchmark executable: {e}")
            sys.exit(1)

    # Create process
    process = Process()
    print(f"Process Command: {benchmark_path} {args.options}")
    if args.options:
        process.cmd = [benchmark_path] + args.options.split()
    else:
        process.cmd = [benchmark_path]
    process.executable = benchmark_path
    process.cwd = os.getcwd()

    # Debug process details
    print(f"Process Executable: {process.executable}")
    print(f"Process Command: {process.cmd}")
    print(f"Process Working Directory: {process.cwd}")

    # Try to run the process directly to debug
    try:
        print("\n=== Direct Process Execution Test ===")
        result = subprocess.run(process.cmd, capture_output=True, text=True, timeout=10)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)
    except subprocess.TimeoutExpired:
        print("Process timed out")
    except Exception as e:
        print(f"Process execution failed: {e}")

    # Set up system workload
    system.workload = SEWorkload.init_compatible(benchmark_path)

    # Set CPU workload
    system.cpu.workload = process
    system.cpu.createThreads()

    # Create root
    root = Root(full_system=False, system=system)

    # Instantiate simulation
    m5.instantiate()

    # Detailed system configuration logging
    def log_system_configuration(system):
        """Log detailed system configuration for debugging"""
        print("\n===== SYSTEM CONFIGURATION DEBUG =====")
        logging.info("Logging System Configuration")
        
        # CPU Configuration
        print(f"CPU Type: {type(system.cpu)}")
        print(f"CPU Clock: {system.cpu.clk_domain.clock}")
        print(f"CPU Voltage Domain: {system.cpu.clk_domain.voltage_domain}")
        
        # Memory Configuration
        print(f"Memory Type: {type(system.membus)}")
        print(f"Memory Latency: {system.membus.width}")
        
        # Workload Details
        print(f"Workload Type: {type(system.workload)}")
        print(f"Executable Path: {system.workload.executable}")
        
        # Branch Predictor Details
        if hasattr(system.cpu, 'branchPred'):
            print(f"Branch Predictor: {type(system.cpu.branchPred)}")
        
        # Functional Units
        if hasattr(system.cpu, 'fuPool'):
            print("Functional Units:")
            for fu in system.cpu.fuPool.FUList:
                print(f"  - {type(fu)}: Count = {fu.count}")
        
        print("=======================================\n")
        logging.info("System Configuration Logging Complete")

    # Call system configuration logging
    log_system_configuration(system)

    # Verify workload is set correctly
    if not system.workload or not system.workload.executable:
        logging.error("No workload executable set!")
        print("CRITICAL ERROR: No workload executable set!")
        sys.exit(1)

    # Additional workload verification
    print("\n===== WORKLOAD VERIFICATION =====")
    print(f"Workload Executable: {system.workload.executable}")
    print(f"Workload Executable Exists: {os.path.exists(system.workload.executable)}")
    print(f"Workload Executable is Executable: {os.access(system.workload.executable, os.X_OK)}")
    print("==================================\n")

    # Modify simulation to add more logging
    def enhanced_simulate():
        """Enhanced simulation with more detailed logging"""
        logging.info("Starting Simulation")
        print("\n===== SIMULATION START =====")
        
        try:
            # Run simulation
            exit_event = m5.simulate()
            
            # Log simulation details
            logging.info(f"Simulation completed. Exit cause: {exit_event.getCause()}")
            print(f"Simulation completed @ tick {m5.curTick()}")
            print(f"Exit Cause: {exit_event.getCause()}")
            
            return exit_event
        except Exception as e:
            log_exception(e)
            raise

    # Replace standard simulation with enhanced version
    exit_event = enhanced_simulate()

    # Print detailed statistics
    print("\n===== SIMULATION STATISTICS =====")
    print(f"Total Simulation Ticks: {m5.curTick()}")
    print(f"Simulation Exit Cause: {exit_event.getCause()}")
    
    # Attempt to print CPU statistics
    try:
        print(f"\nInstructions Executed: {system.cpu.numInsts}")
        print(f"Total Cycles: {system.cpu.numCycles}")
    except Exception as e:
        print(f"Could not retrieve CPU statistics: {e}")
    
    print("===============================\n")

    # Print simulation results
    print(f"\nSimulation complete! Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")

    # Extract and display detailed performance statistics
    print("\n===== PERFORMANCE STATISTICS =====")
    print(f"Simulated instructions: {system.cpu.numInsts}")
    print(f"Simulated cycles: {system.cpu.numCycles}")
    print(f"IPC: {system.cpu.ipc}")
    print(f"CPI: {system.cpu.cpi}")

    # Additional pipeline metrics if debug is enabled
    if args.debug:
        print("\n===== PIPELINE DETAILS =====")
        print(f"Dispatch stalls: {system.cpu.dispatchStallStatus}")
        print(f"IQ full stalls: {system.cpu.iqFullEvents}")
        print(f"ROB full stalls: {system.cpu.robFullEvents}")
        print(f"Rename map full stalls: {system.cpu.renameMapFullEvents}")
        print(f"Commit squashes: {system.cpu.commitSquashedInsts}")
        print(f"Fetch squashes: {system.cpu.fetchSquashedInsts}")

    # Print branch prediction statistics at the end of simulation
    def print_branch_prediction_stats(cpu):
        print("\n===== BRANCH PREDICTION STATISTICS =====")
        try:
            print(f"Total Branches: {cpu.numBranches}")
            print(f"Branch Mispredictions: {cpu.branchMispredicts}")
            
            # Calculate branch prediction accuracy
            if cpu.numBranches > 0:
                accuracy = (cpu.numBranches - cpu.branchMispredicts) / cpu.numBranches * 100
                print(f"Branch Prediction Accuracy: {accuracy:.2f}%")
            
            # Detailed branch prediction breakdown
            if hasattr(cpu.branchPred, 'globalPred'):
                print("\nGlobal Predictor Stats:")
                print(f"Global Mispredictions: {getattr(cpu.branchPred.globalPred, 'mispredicts', 'N/A')}")
            
            if hasattr(cpu.branchPred, 'localPred'):
                print("\nLocal Predictor Stats:")
                print(f"Local Mispredictions: {getattr(cpu.branchPred.localPred, 'mispredicts', 'N/A')}")
        except Exception as e:
            print(f"Error retrieving branch prediction stats: {e}")
        print("=======================================\n")

    # Print branch prediction statistics
    print_branch_prediction_stats(system.cpu)

except Exception as e:
    log_exception(e)
    sys.exit(1)
