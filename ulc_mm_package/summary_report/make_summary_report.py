from io import TextIOWrapper
from csv import DictReader
from typing import Dict, List, Optional
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
import numpy as np
import numpy.typing as npt

from ulc_mm_package.scope_constants import CSS_FILE_NAME, DEBUG_REPORT
from ulc_mm_package.neural_nets.neural_network_constants import YOGO_PRED_THRESHOLD

COLORS = ["#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94", "#f7b6d2"]


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


def make_html_report(
    dataset_name: str,
    experiment_metadata: Dict[str, str],
    per_image_metadata_plot_path: str,
    class_name_to_cell_count: Dict[str, int],
    perc_parasitemia: str,
    parasites_per_ul: str,
    thumbnails: Dict[str, List[str]],
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
        "cell_counts": class_name_to_cell_count,
        "perc_parasitemia": perc_parasitemia,
        "parasites_per_ul": parasites_per_ul,
        "all_thumbnails": thumbnails,
        "DEBUG_SUMMARY_REPORT": DEBUG_REPORT,
        "per_image_metadata_plot_filename": per_image_metadata_plot_path,
        "cell_count_plot_filename": counts_plot_loc,
        "confidence_hists_filename": conf_plot_loc,
        "objectness_hists_filename": objectness_plot_loc,
    }
    content = template.render(context)

    return content


def save_html_report(content: str, save_path: Path) -> None:
    """Save the html report  (as .html) to a specified location on disk.

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
    import os

    def debug(text):
        print(text)

    env = Environment(loader=FileSystemLoader("./"))
    env.filters["debug"] = debug
    template = env.get_template("summary_template.html")

    cell_counts = {
        "Healthy": int(1e6),
        "WBC": int(1e6 / 600),
        "Ring": 0,
        "Trophozoite": 0,
        "Schizont": 0,
        "Gametocyte": 0,
    }

    parasite_folders = [
        "dataset_dir/thumbnails/" + x
        for x in ["ring", "trophozoite", "schizont", "gametocyte"]
    ]

    thumbnails = {
        "Rings": [
            os.path.join(parasite_folders[0], x)
            for x in sorted(os.listdir(parasite_folders[0]))
        ],
        "Trophozoite": [
            os.path.join(parasite_folders[1], x)
            for x in sorted(os.listdir(parasite_folders[1]))
        ],
        "Schizont": [
            os.path.join(parasite_folders[2], x)
            for x in sorted(os.listdir(parasite_folders[2]))
        ],
        "Gametocyte": [
            os.path.join(parasite_folders[3], x)
            for x in sorted(os.listdir(parasite_folders[3]))
        ],
    }

    exp_metadata = {
        "operator_id": "IJ",
        "participant_id": "Also IJ",
        "notes": "blood looks gorgeous. This is a comprehensive note with lots of important details, details which you must commit to memory! This is a comprehensive note with lots of important details, details which you must commit to memory! This is a comprehensive note with lots of important details, details which you must commit to memory!",
        "flowcell_id": "0123-A2",
    }

    per_img_metadata_plot_path = "per_img_metadata_plt.jpg"
    make_per_image_metadata_plots(
        open(
            "/Users/ilakkiyan.jeyakumar/Documents/ulc-malaria-scope/ulc-malaria-scope/experiments_personal/stuck_cells/2023-06-26-181243/2023-06-26-181305_/2023-06-26-181305perimage__metadata.csv",
            "r",
        ),
        per_img_metadata_plot_path,
    )

    pred_tensor = np.load(
        "/Users/ilakkiyan.jeyakumar/Documents/ulc-malaria-scope/ulc-malaria-scope/experiments_personal/high_hemat/2023-07-13-150543/2023-07-13-150641_/2023-07-13-150641_parsed_prediction_tensors.npy"
    )
    counts = "counts.jpg"
    yogo_conf = "yogo_confs.jpg"
    yogo_objectness = "yogo_objectness.jpg"
    make_cell_count_plot(pred_tensor, counts)
    make_yogo_conf_plots(pred_tensor, yogo_conf)
    make_yogo_objectness_plots(pred_tensor, yogo_objectness)

    content = make_html_report(
        dataset_name="2023-07-06-000000",
        experiment_metadata=exp_metadata,
        per_image_metadata_plot_path=per_img_metadata_plot_path,
        class_name_to_cell_count=cell_counts,
        perc_parasitemia="0.000",
        parasites_per_ul="0.000",
        thumbnails=thumbnails,
        counts_plot_loc=counts,
        conf_plot_loc=yogo_conf,
        objectness_plot_loc=yogo_objectness,
        css_path="minimal-table.css",
    )

    with open("test.html", "w") as f:
        f.write(content)

    create_pdf_from_html(Path("test.html"), Path("test.pdf"))
