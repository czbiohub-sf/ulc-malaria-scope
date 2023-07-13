from typing import Dict, List
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa


def make_html_report(
    experiment_metadata: Dict[str, str],
    cell_counts: Dict[str, int],
    thumbnails: Dict[str, List[str]],
) -> str:
    """Generate an html report.

    Parameters
    ----------
    experiment_metadata: Dict[str, str]
        Experiment metadata dict
    cell_counts: Dict[str, int]
        A mapping from type of cell (e.g "Healthy") to
        its cell count
    thumbnails: Dict[str, List[str]]
        A mapping between class name (e.g "Ring", "Trophozoite", etc.)
        to a list of thumbnail filepaths (as strings) of the form described in
        `neural_nets/utils.py, _save_thumbnails_to_disk.

    Returns
    -------
    str
        HTML string
    """

    curr_dir = Path(__file__).parent.resolve()
    template_file = "summary_template.html"
    env = Environment(loader=FileSystemLoader(str(curr_dir)))
    template = env.get_template(template_file)
    context = {
        "dataset_name": "2023-07-06-000000",
        "operator_id": experiment_metadata["operator_id"],
        "participant_id": experiment_metadata["participant_id"],
        "notes": experiment_metadata["notes"],
        "flowcell_id": experiment_metadata["flowcell_id"],
        "cell_counts": cell_counts,
        "all_thumbnails": thumbnails,
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
            os.path.join(parasite_folders[2], x)
            for x in sorted(os.listdir(parasite_folders[2]))
        ],
    }

    context = {
        "dataset_name": "2023-07-06-000000",
        "operator_id": "IJ",
        "participant_id": "Also IJ",
        "notes": "blood looks gorgeous",
        "flowcell_id": "0123-A2",
        "cell_counts": cell_counts,
        "all_thumbnails": thumbnails,
    }
    content = template.render(context)

    with open("test.html", "w") as f:
        f.write(content)

    create_pdf_from_html(Path("test"), Path("test.html"))
