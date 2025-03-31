#!/usr/bin/env python3

import os
import subprocess
import time
import csv

# Define pipeline widths to test
WIDTHS = [1, 2, 4, 8]

# Define branch predictors to test
BP_TYPES = ['TournamentBP']

# Create results directory
os.makedirs("superscalar_results", exist_ok=True)

# CSV file to save results
csv_file = "superscalar_results/comparison_results.csv"
with open(csv_file, "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Width", "Branch Predictor", "Wall Time", "Output"])

# Run simulations with different widths
for width in WIDTHS:
    for bp_type in BP_TYPES:
        print(f"\nRunning simulation with width={width}, bp={bp_type}")
        
        # Run the simulation
        start_time = time.time()
        cmd = ["wsl", "build/x86/gem5.opt", "superscalar_simple.py", f"--width={width}", f"--bp-type={bp_type}"]
        process = subprocess.run(cmd, capture_output=True, text=True)
        wall_time = time.time() - start_time
        
        # Save results
        output = process.stdout + process.stderr
        with open(csv_file, "a", newline='') as f:
            writer = csv.writer(f)
            writer.writerow([width, bp_type, wall_time, output])
        
        # Save detailed output to file
        output_file = f"superscalar_results/width_{width}_{bp_type}.txt"
        with open(output_file, "w") as f:
            f.write(output)
        
        print(f"  Wall time: {wall_time:.2f} seconds")
        print(f"  Output saved to: {output_file}")

print(f"\nAll results saved to: {csv_file}")
print("\nGenerating summary report...")

# Generate summary report
report_file = "superscalar_results/summary_report.txt"
with open(report_file, "w") as f:
    f.write("===== SUPERSCALAR PIPELINE PERFORMANCE COMPARISON =====\n\n")
    
    f.write("WALL TIME COMPARISON:\n")
    f.write("-" * 50 + "\n")
    f.write(f"{'Width':<10} {'TournamentBP':<15} {'LocalBP':<15} {'BiModeBP':<15} {'StaticBP':<15}\n")
    f.write("-" * 70 + "\n")
    
    for width in WIDTHS:
        f.write(f"{width:<10} ")
        for bp_type in BP_TYPES:
            # Find the wall time for this configuration
            with open(csv_file, "r", newline='') as csvf:
                reader = csv.reader(csvf)
                next(reader)  # Skip header
                for row in reader:
                    if int(row[0]) == width and row[1] == bp_type:
                        wall_time = float(row[2])
                        f.write(f"{wall_time:<15.2f} ")
                        break
        f.write("\n")
    
    f.write("\nANALYSIS:\n")
    f.write("1. As pipeline width increases, we expect to see performance improvements\n")
    f.write("   due to increased instruction-level parallelism.\n")
    f.write("2. Different branch predictors may perform better for different workloads.\n")
    f.write("3. The TournamentBP generally provides the best overall performance\n")
    f.write("   as it combines the strengths of local and global history.\n")
    f.write("4. The StaticBP is the simplest but least effective predictor.\n\n")
    
    f.write("CONCLUSION:\n")
    f.write("Superscalar execution with effective branch prediction can significantly\n")
    f.write("improve processor performance by exploiting instruction-level parallelism.\n")
    f.write("However, the actual performance gain depends on the characteristics of the\n")
    f.write("workload and the effectiveness of the branch predictor.\n")

print(f"Summary report generated: {report_file}")
print("\nDone!")
