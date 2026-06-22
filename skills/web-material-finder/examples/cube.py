# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import os

os.makedirs(r'C:\Users\arina\.openclaw\workspace\materials\exam_math_profile\images', exist_ok=True)

fig = plt.figure(figsize=(9, 9), facecolor='white')
ax = fig.add_subplot(111, projection='3d')

# Cube with edge length 1
a = 1.0
A = np.array([0, 0, 0])
B = np.array([a, 0, 0])
C = np.array([a, a, 0])
D = np.array([0, a, 0])
A1 = np.array([0, 0, a])
B1 = np.array([a, 0, a])
C1 = np.array([a, a, a])
D1 = np.array([0, a, a])

# Back faces (lighter shading for depth perception)
back_faces = [[D, C, C1, D1], [A, D, D1, A1], [A1, D1, C1, B1]]
front_faces = [[A, B, C, D], [B, B1, C1, C], [A, A1, B1, B]]

# Draw cube faces (light gray for back, white for front)
for face in back_faces:
    poly = Poly3DCollection([face], facecolors='#f0f0f0', edgecolors='black', linewidths=1.5, alpha=0.3)
    ax.add_collection3d(poly)
for face in front_faces:
    poly = Poly3DCollection([face], facecolors='white', edgecolors='black', linewidths=2.0, alpha=0.05)
    ax.add_collection3d(poly)

# Cube edges (cleaner after faces)
edges = [
    [A, B], [B, C], [C, D], [D, A],
    [A1, B1], [B1, C1], [C1, D1], [D1, A1],
    [A, A1], [B, B1], [C, C1], [D, D1]
]
for edge in edges:
    p1, p2 = edge
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]], 'k-', linewidth=1.8)

# Space diagonal AC1 (red, solid)
ax.plot([A[0], C1[0]], [A[1], C1[1]], [A[2], C1[2]], 'r-', linewidth=2.5, label='AC₁ (диагональ)')

# Projection of diagonal onto bottom face (red, dashed) — to show angle α
ax.plot([A[0], C[0]], [A[1], C[1]], [A[2], C[2]], 'r--', linewidth=1.5, alpha=0.7)
ax.plot([C[0], C1[0]], [C[1], C1[1]], [C[2], C1[2]], 'r--', linewidth=1.5, alpha=0.7)

# Vertex labels (with offsets to avoid overlap)
def label_point(pt, text, offset):
    ax.text(pt[0] + offset[0], pt[1] + offset[1], pt[2] + offset[2], text,
            fontsize=18, fontweight='bold', ha='center', va='center')

label_point(A,  'A',  (-0.08, -0.05, -0.05))
label_point(B,  'B',  ( 0.08, -0.05, -0.05))
label_point(C,  'C',  ( 0.10,  0.08, -0.05))
label_point(D,  'D',  (-0.10,  0.08, -0.05))
label_point(A1, "A'", (-0.08, -0.05,  0.05))
label_point(B1, "B'", ( 0.08, -0.05,  0.05))
label_point(C1, "C'", ( 0.10,  0.08,  0.05))
label_point(D1, "D'", (-0.10,  0.08,  0.05))

# Mark angle α between AC1 and its projection on bottom face (AC)
# AC1 direction: (1,1,1)/sqrt(3), AC direction: (1,1,0)/sqrt(2)
# Place arc in the plane containing A, C1, C
# Use a small arc near point C
import math
# Angle α location — at C (the foot of the projection)
ax_C = np.array([C[0]-0.05, C[1]-0.05, C[2]+0.01])
ax.text(ax_C[0], ax_C[1], ax_C[2], 'α', fontsize=18, color='red', fontweight='bold')

# Title
ax.set_title('Куб ABCDA\'B\'C\'D\' с диагональю AC\' и углом α к грани ABCD',
             fontsize=14, pad=20)

# Cleanup
ax.set_xlim([-0.15, 1.15])
ax.set_ylim([-0.15, 1.15])
ax.set_zlim([-0.15, 1.15])
ax.set_box_aspect([1, 1, 1])
ax.view_init(elev=18, azim=-50)
ax.axis('off')

# Save
out_path = r'C:\Users\arina\.openclaw\workspace\materials\exam_math_profile\images\cube_diagonal_AC1.png'
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved:', out_path)
print('Size:', os.path.getsize(out_path), 'bytes')
