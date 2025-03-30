import m5
from m5.objects import *
from m5.params import *
from m5.proxy import *

class SimplePipeline(MinorCPU):
    type = 'SimplePipeline'
    cxx_header = "cpu/minor/cpu.hh"
    cxx_class = 'gem5::MinorCPU'

    # Pipeline stages configuration
    fetch1LineSnapWidth = 0  # Ensure clean stage boundaries
    fetch1ToFetch2ForwardDelay = 1  # Stage delay between fetch stages
    fetch2ToDecodeForwardDelay = 1  # Delay between fetch and decode
    decodeToExecuteForwardDelay = 1  # Delay between decode and execute
    executeToMemoryForwardDelay = 1  # Delay between execute and memory
    memoryToWritebackForwardDelay = 1  # Delay between memory and writeback

    # Configure execution stage
    executeAllowEarlyMemoryIssue = False  # Enforce in-order memory operations
    executeBranchDelay = 1  # Branch resolution delay
    executeCommitLimit = 2  # Number of instructions that can be committed per cycle
    executeMemoryCommitLimit = 1  # Memory instructions per cycle
    executeInputBufferSize = 4  # Size of input buffer to execute stage
    executeIssueLimit = 1  # Instructions issued per cycle
    executeLSQMaxStoreBufferStoresPerCycle = 1  # Store buffer bandwidth
    executeLSQRequestsQueueSize = 2  # LSQ size
    executeLSQStoreBufferSize = 4  # Store buffer size
    executeLSQTransfersQueueSize = 2  # LSQ transfer queue size
    executeMaxAccessesInMemory = 2  # Maximum number of concurrent memory accesses
    executeMemoryWidth = 1  # Memory operation width
    executeSetTraceTimeOnCommit = True  # Set instruction trace times on commit
    executeSetTraceTimeOnIssue = False  # Don't set trace times on issue

    # Pipeline widths
    decodeInputWidth = 1  # Instructions per cycle at decode input
    decodeToExecuteForwardWidth = 1  # Width between decode and execute
    executeInputWidth = 1  # Instructions per cycle at execute input
    executeCycleInput = True  # Enable cycle-by-cycle input to execute
    fetch1LineWidth = 1  # Instruction fetch width
    fetch1ToFetch2ForwardWidth = 1  # Width between fetch stages
    fetch2InputBufferSize = 2  # Size of fetch2 input buffer
    fetch2ToDecodeForwardWidth = 1  # Width between fetch2 and decode

def createSimplePipeline():
    """Create an instance of the simple pipeline CPU"""
    system = System()
    
    # Set up the clock and voltage domains
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = '1GHz'
    system.clk_domain.voltage_domain = VoltageDomain()
    
    # Create our simple pipeline CPU
    system.cpu = SimplePipeline()
    
    # Create memory bus and connect it to the CPU
    system.membus = SystemXBar()
    system.cpu.icache_port = system.membus.cpu_side_ports
    system.cpu.dcache_port = system.membus.cpu_side_ports
    
    # Create a memory controller and connect it to the bus
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports
    
    return system

# Create the system and CPU
system = createSimplePipeline()

# Enable debug flags for pipeline tracing
m5.debug.flags["MinorTrace"] = True
m5.debug.flags["Pipeline"] = True
m5.debug.flags["Fetch"] = True
m5.debug.flags["Decode"] = True
m5.debug.flags["Execute"] = True

# Create a simple test program (add two numbers)
binary = b'\x48\x83\xc0\x01'  # Simple x86 instruction: add rax, 1

# Write the test program to a temporary file
with open('test.bin', 'wb') as f:
    f.write(binary)

# Set up the process to run
process = Process()
process.cmd = ['test.bin']
system.cpu.workload = process

# Create the root object and start the simulation
root = Root(full_system=False, system=system)

# Instantiate the system and begin execution
m5.instantiate()

# Run the simulation
print("Beginning simulation!")
exit_event = m5.simulate()
print('Exiting @ tick {} because {}'
      .format(m5.curTick(), exit_event.getCause()))
