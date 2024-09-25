import numpy as np
import matplotlib.pyplot as plt


# def plot

if __name__ == "__main__":
    fig, ax1 = plt.subplots( figsize=(10,1.5))

    parasitemia = 45
    bounds = [1, 150]
    lims = [1, 200]

    # TODO replace with gradient blue -> yellow
    # Add confidence bounds
    # broken axis
    colors = [
        'blue',
        'yellow',
        'orange',
        'red',
    ]
    color_cutoffs = [
        10,
        1e2,
        1e3,
        1e6,
    ]
    min = 1

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

    next_min = min
    for color, cutoff in zip(colors, color_cutoffs):
        ax1.axvspan(
            next_min,
            cutoff,
            facecolor=color,
            alpha=0.3,
        )
        next_min = cutoff

    ax1.set_xscale('log')
    ax1.set_xlim(min, color_cutoffs[-1])
    ax1.set_xlabel('parasites / µL')

    ax1.set_yticklabels([])
    ax1.tick_params(axis='y', left=False)

    height = 9
    ax1.text(parasitemia, height, f'{parasitemia}', ha='center', va='bottom', fontweight='bold')
    # ax1.text(bounds[0], height, bounds[0], va='center', ha='center')
    # ax1.text(bounds[1], height, bounds[1], va='center', ha='center')

    plt.tight_layout()
    plt.show()