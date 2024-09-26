import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as patches

from matplotlib.ticker import LogLocator, FixedLocator


from brokenaxes import brokenaxes


XLIMS = [0.1, 1e6]

# Function to filter ticks
def filter_ticks(ticks, min_val, max_val):
    return [tick for tick in ticks if tick <= min_val or tick >= max_val]

def plot_parasitemia(parasitemia, bounds):

    # Background (color gradient)
    fig, ax0 = plt.subplots(figsize=(10,2))
    ax0.axis('off')

    # Define gradient based on colormap
    colors = [(0, "green"), (0.2, "yellow"), (0.8, "orange"), (1,"red")]
    cmap = LinearSegmentedColormap.from_list("custom_gradient", colors)

    gradient_len = 1000
    gradient = np.hstack((np.ones( int(gradient_len/6)), np.linspace(2, 10, gradient_len)))
    gradient = np.vstack((gradient, gradient))

    ax0.imshow(gradient, aspect='auto', extent=(0, 1, -4.25, 6.25), cmap=cmap) # extent manually selected to fit

    # Foreground (box plot)
    ax1 = ax0.twiny()

    ax1.set_xscale('log')
    ax1.set_xlim(0.1, 1e6)
    ax1.set_xlabel('parasites / µL')

    ax1.xaxis.set_label_position('bottom')
    ax1.xaxis.tick_bottom()

    ax1.set_yticklabels([])
    ax1.tick_params(axis='y', left=False)

    # Configure box plot based on parasitemia and 95% conf bounds
    stats = [
        dict(
            med=parasitemia,
            q1=bounds[0],
            q3=bounds[1],
            whislo=parasitemia,
            whishi=parasitemia,
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
    ax1.text(parasitemia, 10, parasitemia, ha='center', va='bottom', fontweight='bold')
    for bound in bounds:
        ax1.text(bound, 7, bound, ha='center', va='bottom', alpha=0.7)

    # Set background plot to match dims of foreground plot
    ax0.set_ylim(ax1.get_ylim())

    # White out axis break
    rect = patches.Rectangle((0.8, -5), 0.2, 80, linewidth=1, edgecolor='none', facecolor='white')
    ax1.add_patch(rect)

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

    # Annotate zero zone
    fig.subplots_adjust(left=0.8)
    trans = ax1.get_xaxis_transform()
    ax1.annotate('0', xy=(0.085, 0.5), ha="center", va="center", xycoords=trans)

    fig.tight_layout()
    return fig

if __name__ == "__main__":
    parasitemia = 12
    bounds = [10, 150]

    plot_parasitemia(parasitemia, bounds)

    # plt.tight_layout()
    plt.show()