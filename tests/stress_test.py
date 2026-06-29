import subprocess
import sys
import time

def run_stress_test(cycles=5):
    print(f"Starting automation stress test matrix: {cycles} consecutive cycles.")
    
    for cycle in range(1, cycles + 1):
        print(f"\n========================================")
        print(f"Starting Cycle {cycle}/{cycles}...")
        print(f"========================================")
        
        start_time = time.time()
        # Run main_job_bot.py as a subprocess to ensure clean process isolation
        result = subprocess.run([sys.executable, "main_job_bot.py"], capture_output=True, text=True, encoding='utf-8')
        duration = time.time() - start_time
        
        print(f"Cycle {cycle} finished in {duration:.2f} seconds.")
        
        if result.returncode != 0:
            print(f"Cycle {cycle} FAILED with exit code {result.returncode}!")
            print("\n--- STDOUT ---")
            try:
                print(result.stdout)
            except Exception:
                print(result.stdout.encode('utf-8'))
            print("\n--- STDERR ---")
            try:
                print(result.stderr)
            except Exception:
                print(result.stderr.encode('utf-8'))
            sys.exit(result.returncode)
            
        print(f"Cycle {cycle} completed successfully!")
        # Print a snippet of the output to verify it succeeded
        last_lines = result.stdout.strip().split("\n")[-10:]
        print("Tail of output:")
        for line in last_lines:
            try:
                print(f"  {line}")
            except Exception:
                print(f"  {line.encode('utf-8')}")
            
        # Polite delay between cycles to avoid hitting rate limits too fast
        if cycle < cycles:
            sleep_time = 5.0
            print(f"Sleeping for {sleep_time}s before the next cycle...")
            time.sleep(sleep_time)
            
    print("\nSTRESS TEST PASSED! All 5 cycles completed successfully without any failures.")

if __name__ == "__main__":
    run_stress_test()
