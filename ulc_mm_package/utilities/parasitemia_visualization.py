import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as patches

from matplotlib.ticker import LogLocator, FixedLocator


XLIM = [0.3, 1e6]
BOUND0 = XLIM[0] + 0.003
CENTER0 = BOUND0 # The x-value centered in the 0 zone


def filter_ticks(ticks, min_val, max_val):
    # Filter tick marks
    return [tick for tick in ticks if tick <= min_val or tick >= max_val]

def format_input(parasitemia, bounds):
    # Make sure all values are rounded
    parasitemia_raw = round(parasitemia)
    bounds_raw = [round(bounds[0]), round(bounds[1])]

    # Reformat parasitemia position based on 0 zone
    parasitemia_plot = CENTER0 if parasitemia_raw==0 else parasitemia_raw
    
    # Reformat bound position based on XLIM zone
    bounds_plot = [BOUND0, bounds[1]] if bounds_raw[0]==0 else bounds_raw

    return parasitemia_raw, bounds_raw, parasitemia_plot, bounds_plot

def plot_parasitemia(parasitemia, bounds):
    # Format values for plotting
    parasitemia_raw, bounds_raw, parasitemia_plot, bounds_plot = format_input(parasitemia, bounds)

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

    # Foreground (box plot)

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

    # Display numbers above plot
    ax1.text(parasitemia_plot, 10, parasitemia_raw, ha='center', va='bottom', fontweight='bold')
    for bound_raw, bound_plot in zip(bounds_raw, bounds_plot):
        ax1.text(bound_plot, 7, bound_raw, ha='center', va='bottom', alpha=0.7)

    # Set background plot to match dims of foreground plot
    ax0.set_ylim(ax1.get_ylim())

    # White out axis break
    rect = patches.Rectangle((0.8, -5), 0.2, 80, linewidth=1, edgecolor='none', facecolor='white')
    ax1.add_patch(rect)

    # Annotate zero zone
    ax1.text(parasitemia_plot, -7, 0, ha='center', va='top')
    # fig.subplots_adjust(left=0.8)
    # trans = ax1.get_xaxis_transform()
    # ax1.annotate('0', xy=(CENTER0, 0), ha="center", va="center", xycoords=trans)

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

    fig.tight_layout()
    return fig

if __name__ == "__main__":
    parasitemia = 0
    bounds = [0, 25]

    plot_parasitemia(parasitemia, bounds)

    # plt.tight_layout()
    plt.show()
