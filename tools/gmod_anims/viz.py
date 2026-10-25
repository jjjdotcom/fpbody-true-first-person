import sys; sys.path.insert(0,'/home/claude/gmodconv')
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

def draw(ax, T, parents, view, title, color='k'):
    # view: 'side' (x forward right, z up) or 'front' (y, z)
    a, b = (0, 2) if view == 'side' else (1, 2)
    for i, p in enumerate(parents):
        if p >= 0:
            ax.plot([T[p][a], T[i][a]], [T[p][b], T[i][b]], '-', color=color, lw=1.5)
    ax.set_aspect('equal'); ax.set_title(title, fontsize=8); ax.grid(alpha=.3)

def panel(rows, path):
    fig, axes = plt.subplots(len(rows), 2, figsize=(6, 3.2 * len(rows)))
    axes = np.atleast_2d(axes)
    for r, (T, parents, title) in enumerate(rows):
        draw(axes[r][0], T, parents, 'side', title + ' (side, +X fwd)')
        draw(axes[r][1], T, parents, 'front', title + ' (front)')
    plt.tight_layout(); plt.savefig(path, dpi=80); plt.close()
