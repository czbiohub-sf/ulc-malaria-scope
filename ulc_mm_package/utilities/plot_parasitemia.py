import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as patches

from matplotlib.ticker import LogLocator, FixedLocator


from brokenaxes import brokenaxes

# def plot

# Function to filter ticks
def filter_ticks(ticks, min_val, max_val):
    return [tick for tick in ticks if tick <= min_val or tick >= max_val]

if __name__ == "__main__":
    fig, ax0 = plt.subplots(figsize=(10,1.5))

    parasitemia = 45
    bounds = [1, 150]
    lims = [1, 200]

    colors = [(0, "green"), (0.2, "yellow"), (0.8, "orange"), (1,"red")]
    cmap = LinearSegmentedColormap.from_list("custom_gradient", colors)

    ax0.axis('off')

    gradient = np.hstack((np.ones( int(1000/6)), np.linspace(2, 10, 1000)))
    print(gradient)
    gradient = np.vstack((gradient, gradient))
    ax1 = ax0.twiny()


    ax0.imshow(gradient, aspect='auto', extent=(0, 1, -4.25, 6.25), cmap=cmap)


    # TODO replace with gradient blue -> yellow
    # Add confidence bounds
    # broken axis for 0

    xlim = [0.1, 1e6]

    stats = [
        dict(
            med=parasitemia,
            q1=bounds[0],
            q3=bounds[1],
            whislo=bounds[0],
            whishi=bounds[1],
            fliers=[]
        )
    ]

    bxp = ax1.bxp(
        stats, 
        medianprops=dict(color='black', linewidth=2),
        boxprops=dict(linewidth=3),
        vert=False,
        widths=10,
    )

    ymin = 0
    ymax = 1

    ax1.set_xscale('log')
    ax1.set_xlim(xlim[0], xlim[1])
    ax1.set_xlabel('parasites / µL')

    ax1.set_yticklabels([])
    ax1.tick_params(axis='y', left=False)

    # ax1.text(1, 1, r'//', fontsize=label_size, zorder=101, horizontalalignment='center', verticalalignment='center')


    height = 9
    ax1.text(parasitemia, height, f'{parasitemia}', ha='center', va='bottom', fontweight='bold')
    # ax1.text(bounds[0], height, bounds[0], va='center', ha='center')
    # ax1.text(bounds[1], height, bounds[1], va='center', ha='center')

    ax0.set_ylim(ax1.get_ylim())
    ax1.xaxis.set_label_position('bottom')
    ax1.xaxis.tick_bottom()

    rect = patches.Rectangle((0.8, -5), 0.2, 80, linewidth=1, edgecolor='none', facecolor='white')
    # ax1.scatter(0.85, -4.25, color='white', marker='s', s=75, clip_on=False, zorder=100)

    # Add the rectangle to the plot
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



    # # Get current tick locations on the x-axis
    # xticks = ax1.get_xticks()

    # # Filter out the ticks within the specified range
    # for tick, loc in zip(ax1.get_xticklines(), ax1.get_xticks()):
    #     if loc < 1:
    #         print(loc)
    #         # tick._label.set_visible(False)
    #         tick.set_visible(False)
    #         print(tick)
    #     # print(new_xticks)
    # # ax1.set_xticks([])  # Remove all ticks

    # ax1.set_xticks([], minor=True)

    # # Set the new ticks (removing those in the specified range)
    # ax1.set_xticks(new_xticks)

    plt.tight_layout()
    plt.show()