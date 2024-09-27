import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import argparse

from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import LogLocator, FixedLocator


XLIM = [0.3, 1e6]
BOUND0 = XLIM[0] + 0.002
CENTER0 = BOUND0 # The x-value centered in the 0 zone


def filter_ticks(ticks, min_val, max_val):
    # Filter tick marks
    return [tick for tick in ticks if tick <= min_val or tick >= max_val]

def format_input(parasitemia, err):
    bounds = [
        parasitemia -  err,
        parasitemia + err,
    ]

    # Round values and truncate to 0
    parasitemia_raw = max(0, round(parasitemia))
    bounds_raw = [max(0, round(bounds[0])), max(0, round(bounds[1]))]

    # Reformat parasitemia position based on 0 zone
    parasitemia_plot = CENTER0 if parasitemia_raw==0 else parasitemia_raw
    
    # Reformat bound position based on XLIM zone
    bounds_plot = [BOUND0 if bound==0 else bound for bound in bounds_raw]

    return parasitemia_raw, bounds_raw, parasitemia_plot, bounds_plot

def make_parasitemia_plot(parasitemia, err, savefile):
    # Format values for plotting
    parasitemia_raw, bounds_raw, parasitemia_plot, bounds_plot = format_input(parasitemia, err)

    # Background (color gradient)
    fig, ax0 = plt.subplots(figsize=(10,2))
    ax0.axis('off')

    # Define gradient based on colormap
    colors = [(0, "green"), (0.2, "yellow"), (0.8, "orange"), (1,"red")]
    cmap = LinearSegmentedColormap.from_list("custom_gradient", colors)

    gradient_len = 1000
    gradient = np.hstack((np.ones(int(gradient_len/14)), np.linspace(2, 10, gradient_len)))
    gradient = np.vstack((gradient, gradient))

    ax0.imshow(gradient, aspect='auto', extent=(0, 1, -4.25, 6.25), cmap=cmap) # extent manually selected to fit

    # Midground (axes)
    ax1 = ax0.twiny()

    ax1.set_xscale('log')
    ax1.set_xlim(XLIM[0], XLIM[1])
    ax1.set_xlabel('parasites / µL')

    ax1.xaxis.set_label_position('bottom')
    ax1.xaxis.tick_bottom()

    ax1.set_yticklabels([])
    ax1.tick_params(axis='y', left=False)

    # # Foreground (box plot)
    # ax1 = ax0.twiny()
    
    # ax1.axis('off')
    # ax1.set_xlim(ax1.get_xlim())
    # ax1.set_xscale('log')

    # Configure box plot based on parasitemia and 95% conf bounds
    stats = [
        dict(
            med=parasitemia_plot,
            q1=bounds_plot[0],
            q3=bounds_plot[1],
            whislo=parasitemia_plot,
            whishi=parasitemia_plot,
            fliers=[]
        )
    ]
    bxp = ax1.bxp(
        stats, 
        medianprops=dict(color='black', linewidth=5),
        boxprops=dict(linewidth=3, alpha=0.5),
        whiskerprops=dict(alpha=0),
        vert=False,
        widths=10,
    )

    # Set background plot to match dims of foreground plot
    ax0.set_ylim(ax1.get_ylim())

    # Display numbers above plot
    ax1.text(parasitemia_plot, 10, parasitemia_raw, ha='center', va='bottom', fontweight='bold')
    ax1.text(bounds_plot[0]*0.9, 6.5, bounds_raw[0], ha='right', va='bottom', alpha=0.7)
    ax1.text(bounds_plot[1]*1.1, 6.5, bounds_raw[1], ha='left', va='bottom', alpha=0.7)

    # Block axis
    for spine in ax1.spines.values():
        spine.set_zorder(0)
    for spine in ax1.spines.values():
        spine.set_visible(False)

    # White out axis break
    rect = patches.Rectangle((0.8, -5), 0.2, 80, linewidth=1, edgecolor='none', facecolor='white', zorder=1)
    ax1.add_patch(rect)

    # Annotate zero zone
    ax1.text(BOUND0, -7, 0, ha='center', va='top')

    # Get and filter major ticks
    major_locator = LogLocator(base=10.0, numticks=100)
    major_ticks = major_locator.tick_values(0.1, 1e6)
    filtered_major_ticks = filter_ticks(major_ticks, 0.01, 1)

    # Get and filter minor ticks
    minor_locator = LogLocator(base=10.0, subs=np.arange(2, 10), numticks=100)
    minor_ticks = minor_locator.tick_values(0.1, 1e6)
    filtered_minor_ticks = filter_ticks(minor_ticks, 0.01, 1)

    # Set the filtered ticks
    ax1.xaxis.set_major_locator(FixedLocator(filtered_major_ticks))
    ax1.xaxis.set_minor_locator(FixedLocator(filtered_minor_ticks))

    fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
    fig.tight_layout()
    plt.savefig(savefile)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('parasitemia')
    parser.add_argument('error')
    parser.add_argument('filename')

    args = parser.parse_args()
    parasitemia = int(args.parasitemia)
    err = int(args.error)

    make_parasitemia_plot(parasitemia, err, args.filename)
