import subprocess
import sys


def run_step(script_name: str):
    print(f"\n=== Running {script_name} ===")
    result = subprocess.run([sys.executable, f"src/{script_name}"])
    if result.returncode != 0:
        print(f"FAILED: {script_name} exited with code {result.returncode}")
        sys.exit(result.returncode)
    print(f"=== {script_name} completed successfully ===")


if __name__ == "__main__":
    run_step("ingest.py")
    run_step("transform.py")
    run_step("load_to_bigquery.py")
    print("\nPipeline completed successfully.")
