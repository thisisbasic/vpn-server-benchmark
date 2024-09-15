import subprocess
import os
import time
import re
import speedtest
import argparse
from tabulate import tabulate


class WireGuardManager:
    def __init__(self, config_path, verbose=False):
        self.config_path = config_path
        self.verbose = verbose

    def __enter__(self):
        """Activates the WireGuard VPN."""
        self.activate_wireguard()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Ensures WireGuard is deactivated upon exit, even if an error occurs."""
        self.deactivate_wireguard()

    def activate_wireguard(self):
        """Activate WireGuard VPN using the given configuration."""
        try:
            if self.verbose:
                subprocess.run(['wg-quick', 'up', self.config_path], check=True)
            else:
                subprocess.run(['wg-quick', 'up', self.config_path], check=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
            print(f"Activated WireGuard config: {self.config_path}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to activate WireGuard config {self.config_path}: {e}")
            raise

    def deactivate_wireguard(self):
        """Deactivate WireGuard VPN."""
        try:
            if self.verbose:
                subprocess.run(['wg-quick', 'down', self.config_path], check=False)
            else:
                subprocess.run(['wg-quick', 'down', self.config_path], check=False, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
            print(f"Deactivated WireGuard config: {self.config_path}")
        except subprocess.CalledProcessError:
            print(f"Failed to deactivate WireGuard (maybe no active connection).")


# Function to test ping latency
def test_latency(target='8.8.8.8', count=5):
    try:
        # Run the ping command
        result = subprocess.run(['ping', '-c', str(count), target], capture_output=True, text=True)

        # Print the full output for debugging (if needed)
        print(result.stdout)

        # Find all 'time=' occurrences in the ping output and extract the values
        times = re.findall(r'time=([\d.]+) ms', result.stdout)

        if times:
            # Convert all extracted times to floats and calculate the average
            latencies = [float(time) for time in times]
            avg_latency = sum(latencies) / len(latencies)
            print(f"Average latency to {target}: {avg_latency:.2f} ms")
            return avg_latency
        else:
            print(f"Could not find latency times in ping output.")
    except Exception as e:
        print(f"Latency test failed: {e}")
    return None


# Function to test speed using speedtest-cli
def test_speed():
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        download_speed = st.download() / 1_000_000  # Convert to Mbps
        upload_speed = st.upload() / 1_000_000  # Convert to Mbps
        print(f"Download speed: {download_speed:.2f} Mbps")
        print(f"Upload speed: {upload_speed:.2f} Mbps")
        return download_speed, upload_speed
    except Exception as e:
        print(f"Speed test failed: {e}")
    return None, None


# Function to benchmark a WireGuard config
def benchmark_config(config_path, verbose=False):
    print(f"\nBenchmarking config: {config_path}")

    # Using the context manager for WireGuard
    with WireGuardManager(config_path, verbose=verbose):
        # Test latency
        latency = test_latency()

        # Test speed
        download_speed, upload_speed = test_speed()

    return {
        'config': config_path,
        'latency': latency,
        'download_speed': download_speed,
        'upload_speed': upload_speed
    }


# Function to display the current benchmark results in a table
def display_results_table(results):
    # Prepare the data for the table
    table_data = []
    for result in results:
        table_data.append([
            os.path.basename(result['config']),
            result['latency'],
            result['download_speed'],
            result['upload_speed']
        ])

    # Print the table using tabulate
    table = tabulate(
        table_data,
        headers=['Config', 'Latency (ms)', 'Download Speed (Mbps)', 'Upload Speed (Mbps)'],
        tablefmt='grid'
    )
    # Clear previous output and display the updated table
    print("\033c", end="")  # Clear terminal
    print(table)
    return table

def save_results_to_file(results_table, filename="results.txt"):
    try:
        # Get the current script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, filename)

        # Write the results to the file
        with open(file_path, "w") as file:
            file.write(results_table)

        print(f"Results saved to {file_path}")
    except Exception as e:
        print(f"Failed to save results to file: {e}")


# Main function to iterate over WireGuard configs and benchmark them
def main(config_folder, country_codes, verbose=False):
    # Keep track of valid configurations to benchmark
    valid_configs = []

    # Process each country code
    for country_code in country_codes:
        # List all .conf files that start with the current country code
        config_files = [f for f in os.listdir(config_folder) if f.endswith('.conf') and f.startswith(country_code)]

        if not config_files:
            # If no config files are found for this country, report it and skip
            print(f"Warning: No configuration files found for country: {country_code}")
            continue

        # Add the valid configuration paths to the list
        valid_configs.extend([os.path.join(config_folder, f) for f in config_files])

    if not valid_configs:
        print("No valid configurations found for any of the provided country codes.")
        return

    results = []
    try:
        for config_path in valid_configs:
            result = benchmark_config(config_path, verbose=verbose)
            if result:
                results.append(result)
                display_results_table(results)  # Display the table after each benchmark
                time.sleep(5)  # Wait a bit before testing the next config

        # Sort results by download speed (descending), then latency (ascending)
        results.sort(key=lambda x: (-x['download_speed'], x['latency']))

    except KeyboardInterrupt:
        print("\nBenchmarking interrupted by user.")

    finally:
        # Ensure any active VPN is deactivated if interrupted
        if valid_configs:
            last_config_path = valid_configs[-1]  # Get the last tested config
            try:
                subprocess.run(['wg-quick', 'down', last_config_path], check=False, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
                print(f"Gracefully disconnected from {os.path.basename(last_config_path)}")
            except subprocess.CalledProcessError:
                print(f"Failed to deactivate WireGuard for {os.path.basename(last_config_path)}")

    # Final results table
    print("\nFinal Benchmark Results:")
    final_table = display_results_table(results)
    save_results_to_file(final_table)


if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Benchmark WireGuard VPN configurations.")
    parser.add_argument('config_folder', type=str, help="Folder containing WireGuard .conf files")
    parser.add_argument('country_codes', type=str, nargs='+',
                        help="Country codes to filter configurations (e.g., 'us', 'ch')")
    parser.add_argument('--verbose', action='store_true', help="Enable verbose output for WireGuard commands")

    args = parser.parse_args()

    # Run the benchmark with the provided folder and country codes
    main(args.config_folder, args.country_codes, verbose=args.verbose)
