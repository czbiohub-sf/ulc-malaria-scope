from io import TextIOWrapper
from csv import DictReader
from os import remove
from typing import Dict, List, Optional
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
import numpy as np
import numpy.typing as npt
import argparse

from ulc_mm_package.scope_constants import CSS_FILE_NAME, DEBUG_REPORT, RBCS_PER_UL
from ulc_mm_package.neural_nets.neural_network_constants import (
    YOGO_PRED_THRESHOLD,
    YOGO_CLASS_LIST,
    CLASS_IDS_FOR_THUMBNAILS,
    ASEXUAL_PARASITE_CLASS_IDS,
)
from ulc_mm_package.summary_report.parasitemia_visualization import make_parasitemia_plot

from stats_utils.compensator import CountCompensator

COLORS = ["#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94", "#f7b6d2"]

# Non-interactive backend meant for writing files only
# Adding this here to silence matplotlib's warning about opening figures
# in threads other than the main one.
# This warning is raised whenever we're generating and saving plots to the disk
# for use in the end-of-run summary report.
matplotlib.use("agg")


def format_cell_counts(cell_counts: npt.NDArray) -> Dict[str, str]:
    """Format raw cell counts for display in summary report"""
    # Express parasite classes as percent of total parasites
    total_parasites = np.sum(cell_counts[ASEXUAL_PARASITE_CLASS_IDS])
    
    if total_parasites > 0:
        str_cell_counts = [
            f"{ct} ({ct / total_parasites * 100.0:.3f}% of parasites)"
            if i in ASEXUAL_PARASITE_CLASS_IDS
            else f"{ct}"
            for i, ct in enumerate(
                [
                    ct if i in CLASS_IDS_FOR_THUMBNAILS else 0
                    for i, ct in enumerate(cell_counts)
                ]
            )
        ]
    else:
        str_cell_counts = [
            f"{ct}" if i in CLASS_IDS_FOR_THUMBNAILS else 0
            for i, ct in enumerate(cell_counts)
        ]

    # Add class name
    class_name_to_cell_count = {
        YOGO_CLASS_LIST[i].capitalize(): ct for (i, ct) in enumerate(str_cell_counts)
    }

    return class_name_to_cell_count


def make_per_image_metadata_plots(
    per_image_metadata_file: Optional[TextIOWrapper], save_loc: str
) -> None:
    """Create and save per-image metadata plots to the summary report directory.

    Parameters
    ----------
    per_image_metadata_file: TextIOWrapper
        The opened (i.e open("filename", "r")) per-image metadata csv file.
    save_loc: Path
    """

    if per_image_metadata_file is None:
        raise ValueError("Per image metadata can't be none.")

    reader = DictReader(per_image_metadata_file)
    rows = list(reader)

    flowrates = [x["flowrate"] for x in rows]
    motor_pos = [x["motor_pos"] for x in rows]
    frames_and_flowrates = [(i, float(v)) for i, v in enumerate(flowrates) if v != ""]
    frames_and_motor_pos = [(i, float(v)) for i, v in enumerate(motor_pos) if v != ""]

    fig, ax = plt.subplots(1, 2, figsize=(12, 4))

    ### Flowrate plot
    frames = [x[0] for x in frames_and_flowrates]
    flowrates = [x[1] for x in frames_and_flowrates]
    mean = np.mean(flowrates)
    sd = np.std(flowrates)
    ax[0].plot(frames, flowrates, color="C0", label=f"{mean:.2f} +/- {sd:.2f}")
    ax[0].set_title("Flowrate vs. frame count")
    ax[0].set_xlabel("Frame index")
    ax[0].set_ylabel("Flowrate value ('Image hts/second')")
    ax[0].spines["top"].set_visible(False)
    ax[0].spines["right"].set_visible(False)
    ax[0].legend()

    ### Motor position plot
    frames = [x[0] for x in frames_and_motor_pos]
    motor_pos = [x[1] for x in frames_and_motor_pos]
    ax[1].plot(frames, motor_pos, color="C1")
    ax[1].set_title("Motor position vs. frame count")
    ax[1].set_xlabel("Frame index")
    ax[1].set_ylabel("Motor position")
    ax[1].spines["top"].set_visible(False)
    ax[1].spines["right"].set_visible(False)

    plt.savefig(f"{str(save_loc)}")
    plt.close()


def make_cell_count_plot(preds: npt.NDArray, save_loc: str) -> None:
    """Create cell counts plot.

    Parameters
    ----------
    preds: npt.NDArray
        Parsed predictions, (5 + N classes x NUM_PREDS)
    save_loc: str
        Where to save the plot
    """
    vals = np.cumsum(np.unique(preds[0, :], return_counts=True)[1])
    num_frames = len(np.unique(preds[0, :]))
    x_vals = np.linspace(0, num_frames, num_frames)
    m, b = np.polyfit(x_vals, vals, deg=1)

    def f(x):
        return m * x + b

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(vals, "o", c=COLORS[0], markersize=2, label="Raw vals")
    ax.plot(f(x_vals), c=COLORS[1], label=f"Fit: {m:.2f}x+{b:.2f}")
    ax.set_xlabel("Frame number")
    ax.set_ylabel("Total cells counted")
    ax.set_title("Total cells counted vs. frame number")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.legend()

    plt.savefig(f"{str(save_loc)}")
    plt.close()


def make_yogo_conf_plots(preds: npt.NDArray, save_loc: str) -> None:
    """Create histograms for confidences by class.

    Parameters
    ----------
    preds: npt.NDArray
        Prediction tensor (i.e result from PredictionsHandler().get_prediction_tensors())
    save_loc: Path
    """

    fig, _ = plt.subplots(1, 3, figsize=(12, 12))
    gs = gridspec.GridSpec(4, 4, fig)
    ax1 = plt.subplot(gs[0, 0:2])
    ax2 = plt.subplot(gs[0, 2:])
    ax3 = plt.subplot(gs[1, 0:2])
    ax4 = plt.subplot(gs[1, 2:])
    ax5 = plt.subplot(gs[2, 0:2])
    ax6 = plt.subplot(gs[2, 2:])
    ax7 = plt.subplot(gs[3, 1:3])
    axes = [ax1, ax2, ax3, ax4, ax5, ax6, ax7]
    num_bins = 50

    # Common formatting
    [ax.spines["top"].set_visible(False) for ax in axes]
    [ax.spines["right"].set_visible(False) for ax in axes]
    [ax.set_xlabel("Confidence value") for ax in axes]
    [ax.set_xlim(0, 1) for ax in axes]

    ax1.set_title("Healthy confidences")
    ax1.set_ylabel("Counts (log scale)")
    if len(preds[7, preds[6, :] == 0] > 0):
        ax1.set_yscale("log")
    ax1.hist(
        preds[7, preds[6, :] == 0], bins=num_bins, color=COLORS[0], edgecolor="black"
    )

    ax2.set_title("Ring confidences")
    ax2.set_ylabel("Count")
    ax2.hist(
        preds[7, preds[6, :] == 1], bins=num_bins, color=COLORS[1], edgecolor="black"
    )

    ax3.set_title("Troph confidences")
    ax3.set_ylabel("Count")
    ax3.hist(
        preds[7, preds[6, :] == 2], bins=num_bins, color=COLORS[2], edgecolor="black"
    )

    ax4.set_title("Schizont confidences")
    ax4.set_ylabel("Count")
    ax4.hist(
        preds[7, preds[6, :] == 3], bins=num_bins, color=COLORS[3], edgecolor="black"
    )

    ax5.set_title("Gametocyte confidences")
    ax5.set_ylabel("Count")
    ax5.hist(
        preds[7, preds[6, :] == 4], bins=num_bins, color=COLORS[4], edgecolor="black"
    )

    ax6.set_title("WBC confidences")
    ax6.set_ylabel("Count (log scale)")
    if len(preds[7, preds[6, :] == 5]) > 0:
        ax6.set_yscale("log")
    ax6.hist(
        preds[7, preds[6, :] == 5], bins=num_bins, color=COLORS[5], edgecolor="black"
    )

    ax7.set_title("Misc confidences")
    ax7.set_ylabel("Count")
    ax7.hist(
        preds[7, preds[6, :] == 6], bins=num_bins, color=COLORS[6], edgecolor="black"
    )

    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    plt.savefig(f"{str(save_loc)}")
    plt.close()


def make_yogo_objectness_plots(preds: npt.NDArray, save_loc: str) -> None:
    """Create histograms for objectness by class.

    Parameters
    ----------
    preds: npt.NDArray
        Prediction tensor (i.e result from PredictionsHandler().get_prediction_tensors())
    save_loc: Path
    """

    fig, _ = plt.subplots(1, 3, figsize=(12, 12))
    gs = gridspec.GridSpec(4, 4, fig)
    ax1 = plt.subplot(gs[0, 0:2])
    ax2 = plt.subplot(gs[0, 2:])
    ax3 = plt.subplot(gs[1, 0:2])
    ax4 = plt.subplot(gs[1, 2:])
    ax5 = plt.subplot(gs[2, 0:2])
    ax6 = plt.subplot(gs[2, 2:])
    ax7 = plt.subplot(gs[3, 1:3])
    axes = [ax1, ax2, ax3, ax4, ax5, ax6, ax7]
    num_bins = 50

    # Common formatting
    [ax.spines["top"].set_visible(False) for ax in axes]
    [ax.spines["right"].set_visible(False) for ax in axes]
    [ax.set_xlabel("Objectness value") for ax in axes]
    [ax.set_xlim(YOGO_PRED_THRESHOLD, 1) for ax in axes]
    [ax.set_ylabel("Count") for ax in axes]

    ax1.set_title("Healthy objectness values")
    ax1.hist(
        preds[5, preds[6, :] == 0], bins=num_bins, color=COLORS[0], edgecolor="black"
    )

    ax2.set_title("Ring objectness values")
    ax2.hist(
        preds[5, preds[6, :] == 1], bins=num_bins, color=COLORS[1], edgecolor="black"
    )

    ax3.set_title("Troph objectness values")
    ax3.hist(
        preds[5, preds[6, :] == 2], bins=num_bins, color=COLORS[2], edgecolor="black"
    )

    ax4.set_title("Schizont objectness values")
    ax4.hist(
        preds[5, preds[6, :] == 3], bins=num_bins, color=COLORS[3], edgecolor="black"
    )

    ax5.set_title("Gametocyte objectness values")
    ax5.hist(
        preds[5, preds[6, :] == 4], bins=num_bins, color=COLORS[4], edgecolor="black"
    )

    ax6.set_title("WBC objectness values")
    ax6.hist(
        preds[5, preds[6, :] == 5], bins=num_bins, color=COLORS[5], edgecolor="black"
    )

    ax7.set_title("Misc objectness values")
    ax7.hist(
        preds[5, preds[6, :] == 6], bins=num_bins, color=COLORS[6], edgecolor="black"
    )

    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    plt.savefig(f"{str(save_loc)}")
    plt.close()


def make_html_report(
    dataset_name: str,
    experiment_metadata: Dict[str, str],
    per_image_metadata_plot_path: str,
    cell_counts: npt.NDArray,
    thumbnails: Dict[str, List[str]],
    parasitemia_plot_loc: str,
    counts_plot_loc: str,
    conf_plot_loc: str,
    objectness_plot_loc: str,
    css_path: Optional[str] = CSS_FILE_NAME,
) -> str:
    """Generate an html report.

    Parameters
    ----------
    dataset_name: str
        Typically the timestamp of the dataset
    experiment_metadata: Dict[str, str]
        Experiment metadata dict
    total_rbcs: int
    class_name_to_cell_counts: Dict[str, int]
        Mapping from class name (e.g "Healthy") to number of cells
    perc_parasitemia: str
        Formatted string of the estimated parasitemia (e.g "0.0123")
    parasites_per_ul: str
        Formatted string of the # of parasites per microlitre
    thumbnails: Dict[str, List[str]]
        A mapping between class name (e.g "Ring", "Trophozoite", etc.)
        to a list of thumbnail filepaths (as strings) of the form described in
        `neural_nets/utils.py, _save_thumbnails_to_disk.
    yogo_conf_plot_path: str
        Path to the YOGO confidence histogram plot
    yogo_objectness_plot_path: str
        Path to the YOGO objectness histogram plot
    css_path: Optional[str] = CSS_FILE_NAME
        Optionally specify where the CSS file lives

    Returns
    -------
    str
        HTML string
    """

    curr_dir = Path(__file__).parent.resolve()
    template_file = "summary_template.html"
    env = Environment(loader=FileSystemLoader(str(curr_dir)))
    template = env.get_template(template_file)

    # Explicitly specify "-" otherwise the PDF's table formatting ends up weird
    operator = (
        experiment_metadata["operator_id"]
        if experiment_metadata["operator_id"]
        else "-"
    )
    participant = (
        experiment_metadata["participant_id"]
        if experiment_metadata["participant_id"]
        else "-"
    )
    notes = experiment_metadata["notes"] if experiment_metadata["notes"] else "-"
    fc_id = (
        experiment_metadata["flowcell_id"]
        if experiment_metadata["flowcell_id"]
        else "-"
    )

    context = {
        "css_file": css_path,
        "dataset_name": dataset_name,
        "operator_id": operator,
        "participant_id": participant,
        "notes": notes,
        "flowcell_id": fc_id,
        "class_name_to_cell_count": format_cell_counts(cell_counts),
        "parasites_per_ul_scaling_factor": f"{RBCS_PER_UL:.0E}",
        "all_thumbnails": thumbnails,
        "DEBUG_SUMMARY_REPORT": DEBUG_REPORT,
        "per_image_metadata_plot_filename": per_image_metadata_plot_path,
        "parasitemia_plot_filename": parasitemia_plot_loc,
        "cell_count_plot_filename": counts_plot_loc,
        "confidence_hists_filename": conf_plot_loc,
        "objectness_hists_filename": objectness_plot_loc,
    }
    content = template.render(context)

    return content


def save_html_report(content: str, save_path: Path) -> None:
    """Save the html report (as .html) to a specified location on disk.

    Parameters
    ----------
    content: str
        HTML report string
    save_path: Path
        Location to save .html file
    """

    try:
        with open(save_path, "w") as f:
            f.write(content)
    except Exception as e:
        raise IOError(f"Error when writing html report to: {save_path}. Error: {e}")


def create_pdf_from_html(path_to_html: Path, save_path: Path) -> None:
    """Create a .pdf file from a .html file

    Parameters
    ----------
    path_to_html: Path
    save_path: Path
    """

    with open(save_path, "w+b") as f:
        with open(path_to_html, "r") as f2:
            pisa.CreatePDF(f2, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("path", default="")
    args = parser.parse_args()

    base_path = Path(args.path)
    parasitemia_file = base_path / "parasitemia.jpg"
    html_file = base_path / "test.html"
    pdf_file = base_path / "test.pdf"

    # Dummy data
    exp_metadata = {
        "operator_id": "MK",
        "participant_id": "1034",
        "notes": "sample only",
        "flowcell_id": "A5",
    }
    cell_counts = np.array([148293, 121, 0, 0, 1, 523, 472])

    # Compensator
    compensator = CountCompensator(
        "elated-smoke-4492",
        clinical=True,
        skip=True,
        conf_thresh=0.9,
    )
    (
        comp_parasitemia,
        comp_parasitemia_err,
    ) = compensator.get_res_from_counts(cell_counts, units_ul_out=True)
    make_parasitemia_plot(comp_parasitemia, comp_parasitemia_err, parasitemia_file)

    content = make_html_report(
        "Dummy test",
        exp_metadata,
        "",
        cell_counts,
        {},
        parasitemia_file,
        "",
        "",
        "",
    )
    save_html_report(content, html_file)
    pdf = create_pdf_from_html(html_file, pdf_file)

    remove(html_file)
    remove(parasitemia_file)