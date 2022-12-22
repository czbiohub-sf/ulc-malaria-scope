"""
	Utility for plotting zarr queue size and runtimes/looptimes

	This script gets data from the following files:

		.txt file: 
			Zarrwriter queue size
			Expected format: 
				"zw executor qsize <queue size>"

		.log file
			Runtime (time to run '_run_experiment') and looptimes (time between calls to '_run_experiment')
			Expected formats:
				<timestamp> - DEBUG - Runtime for run_experiment was <runtime> [ulc_mm_package.QtGUI.scope_op]
				<timestamp> - DEBUG - Time between run_experiment calls was <looptime> [ulc_mm_package.QtGUI.scope_op]
					OR
				<timestamp> - DEBUG - Loop time was <looptime> [ulc_mm_package.QtGUI.scope_op]

	Note that this format is now obsolete, and this script should only used for analyzing old datasets.
	Timing and queue size is now saved to metadata, which can be parsed using 'metadata_parser.py' instead.


	Arguments:
		descriptor - Description of dataset
		qsizes_file - File containing queue size data. 
		times_file - File contining timing data

		Both files should be saved under 'utilities/data' and follow the format for .txt and .log files above

	Outputs:
		Prints mean and variance of each dataset, and plots all data.
        The plot is displayed and saved under '/utilities/results/'.

"""

import numpy as np
import matplotlib.pyplot as plt

from os import path


def log_parser(descriptor, qsizes_file, times_file):
    # Get dataset location
    qsizes_filepath = path.join("data", qsizes_file)
    times_filepath = path.join("data", times_file)

    # Parse queue sizes
    f = open(qsizes_filepath, "r")
    for i in range(0, 3):
        f.readline()
    lines = [line.split() for line in f]
    qsizes = [float(line[3]) for line in lines if line[0] == "zw"]

    # Parse timing info
    f = open(times_filepath, "r")
    lines = [line.split() for line in f]
    runtimes = [float(line[8]) * 1000 for line in lines if line[4] == "Runtime"]
    looptimes = [float(line[9]) * 1000 for line in lines if line[5] == "between"]
    if (not runtimes) and (not looptimes):
        looptimes = [float(line[7]) * 1000 for line in lines if line[4] == "Loop"]

    # Plot timing results
    fig, time_ax = plt.subplots()
    time_ax.set_xlabel("Frame #")
    time_ax.set_ylabel("Time (ms)")

    time_ax.scatter(range(0, len(runtimes)), runtimes, label="Runtimes", s=2)
    time_ax.scatter(range(0, len(looptimes)), looptimes, label="Looptimes", s=2)

    # Delineate expected looptimes
    time_ax.plot(
        [0, max(len(runtimes), len(looptimes))], [33, 33], linestyle="--", color="gray"
    )
    time_ax.plot(
        [0, max(len(runtimes), len(looptimes))], [66, 66], linestyle="--", color="gray"
    )

    # Plot size results
    size_ax = time_ax.twinx()
    size_ax.scatter(
        range(0, len(qsizes)), qsizes, label="Queue size", color="green", s=2
    )

    # Format plots
    time_ax.legend(loc=2)
    size_ax.legend(loc=1)
    plt.title(f"Timing and queue size data ({descriptor})")

    # Save/print results
    fig.savefig(path.join("results", f"plots-{descriptor}.png"))
    print(f"Stats for {descriptor}")
    print(f"Queue size: mean={np.mean(qsizes):.2f}, variance={np.var(qsizes):.2f}")
    if looptimes:
        print(
            f"Looptimes: mean={np.mean(looptimes):.2f}, variance={np.var(looptimes):.2f}"
        )
    if runtimes:
        print(
            f"Runtimes: mean={np.mean(runtimes):.2f}, variance={np.var(runtimes):.2f}"
        )

    plt.show()


if __name__ == "__main__":
    # Select dataset (feel free to redefine this dictionary with your files of interest)
    pairs = {
        "zarrwriter": [
            "test-zarrwriter-tester.txt",
            "2022-12-19-160314-zarrwriter-tester.log",
        ],
        "master": ["test-master.txt", "2022-12-19-163708-master.log"],
        "pre-reboot": ["test-pre-reboot.txt", "2022-12-19-165922-pre-reboot.log"],
        "post-reboot": ["test-post-reboot.txt", "2022-12-19-171235-post-reboot.log"],
    }
    selection = "master"

    # Run plotter
    log_parser(selection, pairs[selection][0], pairs[selection][1])
