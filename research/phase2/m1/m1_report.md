# M1 — B0/B1 scoring report (round 1)

**Gold set: AGENT-LABELED** (two independent passes, PROTOCOL v1.1 — this is agent self-consistency, not human agreement). n = 170 pairs. Pinned 170 set (42215fc5969e600e), corpus 005d425e890b30a1.

## Headline

- **B1 (TF-IDF cosine, customer turns only) **PASSES the frozen bar**.**
- Selected operating point: pool iff cosine `>= 0.175964` → **recall_sm = 0.729**, **FFR = 0.095**, pairwise F1 = 0.721
- Bar-passing thresholds on the sweep: 18
- B0 oracle (same subflow): recall_sm = 1.000, FFR = 0.048, F1 = 0.883 (ceiling reference)
- Inter-pass disagreement: 21/170 (0.1235)
- Canonical label counts: related-but-different=38, same-problem=69, unrelated=63

### Interpretation

B1 meets the frozen bar, so per the method doc the finding is: **problem shape is lexical on this data** — a small embedding (B2) adds cost, not value, and is **dropped** (that is a result, not a shortcut).

## B1 operating curve (full sweep)

| threshold | n_pooled | recall_sm | FFR | ambiguous | should-not-match | precision | F1 |
|---|---|---|---|---|---|---|---|
| none (pool nothing) | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| >= 0.000000 | 170 | 1.000 | 1.000 | 1.000 | 1.000 | 0.406 | 0.577 |
| >= 0.004188 | 168 | 1.000 | 0.968 | 1.000 | 0.961 | 0.411 | 0.582 |
| >= 0.011678 | 167 | 1.000 | 0.952 | 0.971 | 0.961 | 0.413 | 0.585 |
| >= 0.014855 | 166 | 1.000 | 0.936 | 0.971 | 0.941 | 0.416 | 0.587 |
| >= 0.017055 | 165 | 1.000 | 0.921 | 0.971 | 0.922 | 0.418 | 0.590 |
| >= 0.020937 | 164 | 1.000 | 0.905 | 0.971 | 0.902 | 0.421 | 0.592 |
| >= 0.035049 | 163 | 1.000 | 0.889 | 0.941 | 0.902 | 0.423 | 0.595 |
| >= 0.042830 | 162 | 1.000 | 0.873 | 0.941 | 0.882 | 0.426 | 0.597 |
| >= 0.042920 | 161 | 1.000 | 0.857 | 0.941 | 0.863 | 0.429 | 0.600 |
| >= 0.043391 | 160 | 1.000 | 0.841 | 0.941 | 0.843 | 0.431 | 0.603 |
| >= 0.046312 | 159 | 1.000 | 0.825 | 0.941 | 0.824 | 0.434 | 0.605 |
| >= 0.046732 | 158 | 1.000 | 0.809 | 0.912 | 0.824 | 0.437 | 0.608 |
| >= 0.053877 | 157 | 1.000 | 0.794 | 0.912 | 0.804 | 0.440 | 0.611 |
| >= 0.055031 | 156 | 1.000 | 0.778 | 0.912 | 0.784 | 0.442 | 0.613 |
| >= 0.055312 | 155 | 1.000 | 0.762 | 0.912 | 0.765 | 0.445 | 0.616 |
| >= 0.057434 | 154 | 0.988 | 0.746 | 0.912 | 0.765 | 0.448 | 0.619 |
| >= 0.058699 | 153 | 0.988 | 0.730 | 0.882 | 0.765 | 0.451 | 0.622 |
| >= 0.059983 | 152 | 0.988 | 0.714 | 0.882 | 0.745 | 0.454 | 0.624 |
| >= 0.062274 | 151 | 0.977 | 0.714 | 0.882 | 0.745 | 0.450 | 0.618 |
| >= 0.063545 | 150 | 0.977 | 0.714 | 0.853 | 0.745 | 0.453 | 0.621 |
| >= 0.063739 | 149 | 0.977 | 0.698 | 0.853 | 0.726 | 0.456 | 0.624 |
| >= 0.064333 | 148 | 0.977 | 0.698 | 0.853 | 0.706 | 0.460 | 0.627 |
| >= 0.065384 | 147 | 0.977 | 0.682 | 0.853 | 0.686 | 0.463 | 0.630 |
| >= 0.068402 | 146 | 0.977 | 0.667 | 0.824 | 0.686 | 0.466 | 0.633 |
| >= 0.069161 | 145 | 0.977 | 0.667 | 0.794 | 0.686 | 0.469 | 0.635 |
| >= 0.070681 | 144 | 0.977 | 0.667 | 0.765 | 0.686 | 0.472 | 0.638 |
| >= 0.070693 | 143 | 0.977 | 0.651 | 0.765 | 0.667 | 0.475 | 0.641 |
| >= 0.071310 | 142 | 0.977 | 0.635 | 0.735 | 0.667 | 0.479 | 0.644 |
| >= 0.076507 | 141 | 0.977 | 0.619 | 0.735 | 0.647 | 0.482 | 0.648 |
| >= 0.077583 | 140 | 0.977 | 0.603 | 0.735 | 0.627 | 0.486 | 0.651 |
| >= 0.077630 | 139 | 0.977 | 0.587 | 0.706 | 0.627 | 0.489 | 0.654 |
| >= 0.078299 | 138 | 0.977 | 0.571 | 0.706 | 0.608 | 0.493 | 0.657 |
| >= 0.078788 | 137 | 0.977 | 0.556 | 0.706 | 0.588 | 0.496 | 0.660 |
| >= 0.079010 | 136 | 0.977 | 0.540 | 0.706 | 0.569 | 0.500 | 0.663 |
| >= 0.080288 | 135 | 0.977 | 0.524 | 0.706 | 0.549 | 0.504 | 0.667 |
| >= 0.081159 | 134 | 0.965 | 0.524 | 0.706 | 0.549 | 0.507 | 0.670 |
| >= 0.084430 | 133 | 0.953 | 0.508 | 0.706 | 0.549 | 0.511 | 0.673 |
| >= 0.086889 | 132 | 0.941 | 0.508 | 0.706 | 0.549 | 0.515 | 0.677 |
| >= 0.089139 | 131 | 0.941 | 0.492 | 0.706 | 0.529 | 0.519 | 0.680 |
| >= 0.091131 | 130 | 0.929 | 0.492 | 0.706 | 0.529 | 0.515 | 0.673 |
| >= 0.091995 | 129 | 0.929 | 0.476 | 0.706 | 0.510 | 0.519 | 0.677 |
| >= 0.092761 | 128 | 0.929 | 0.460 | 0.676 | 0.510 | 0.523 | 0.680 |
| >= 0.094886 | 127 | 0.929 | 0.444 | 0.647 | 0.510 | 0.528 | 0.684 |
| >= 0.095815 | 126 | 0.929 | 0.444 | 0.618 | 0.510 | 0.532 | 0.687 |
| >= 0.095838 | 125 | 0.929 | 0.444 | 0.588 | 0.510 | 0.536 | 0.691 |
| >= 0.096951 | 124 | 0.929 | 0.429 | 0.588 | 0.490 | 0.540 | 0.694 |
| >= 0.097043 | 123 | 0.918 | 0.413 | 0.588 | 0.490 | 0.545 | 0.698 |
| >= 0.100976 | 122 | 0.918 | 0.397 | 0.588 | 0.471 | 0.549 | 0.702 |
| >= 0.103323 | 121 | 0.918 | 0.381 | 0.588 | 0.451 | 0.554 | 0.705 |
| >= 0.103537 | 120 | 0.906 | 0.381 | 0.588 | 0.451 | 0.550 | 0.698 |
| >= 0.103633 | 119 | 0.906 | 0.365 | 0.588 | 0.431 | 0.555 | 0.702 |
| >= 0.104888 | 118 | 0.906 | 0.349 | 0.588 | 0.412 | 0.559 | 0.706 |
| >= 0.106618 | 117 | 0.894 | 0.349 | 0.588 | 0.412 | 0.556 | 0.699 |
| >= 0.107514 | 116 | 0.882 | 0.349 | 0.588 | 0.412 | 0.552 | 0.692 |
| >= 0.107753 | 115 | 0.882 | 0.333 | 0.588 | 0.392 | 0.556 | 0.696 |
| >= 0.109246 | 114 | 0.882 | 0.318 | 0.588 | 0.372 | 0.561 | 0.700 |
| >= 0.112802 | 113 | 0.871 | 0.318 | 0.588 | 0.372 | 0.557 | 0.692 |
| >= 0.113802 | 112 | 0.859 | 0.318 | 0.588 | 0.372 | 0.554 | 0.685 |
| >= 0.115160 | 111 | 0.859 | 0.302 | 0.588 | 0.353 | 0.559 | 0.689 |
| >= 0.115429 | 110 | 0.859 | 0.286 | 0.559 | 0.353 | 0.564 | 0.693 |
| >= 0.117438 | 109 | 0.859 | 0.270 | 0.559 | 0.333 | 0.569 | 0.697 |
| >= 0.118614 | 108 | 0.859 | 0.270 | 0.529 | 0.333 | 0.574 | 0.701 |
| >= 0.121795 | 107 | 0.859 | 0.254 | 0.529 | 0.314 | 0.579 | 0.705 |
| >= 0.124996 | 106 | 0.859 | 0.238 | 0.529 | 0.294 | 0.585 | 0.709 |
| >= 0.126039 | 105 | 0.847 | 0.238 | 0.529 | 0.294 | 0.581 | 0.701 |
| >= 0.126251 | 104 | 0.847 | 0.222 | 0.529 | 0.275 | 0.587 | 0.705 |
| >= 0.127653 | 103 | 0.835 | 0.222 | 0.529 | 0.275 | 0.583 | 0.698 |
| >= 0.128475 | 102 | 0.835 | 0.206 | 0.529 | 0.255 | 0.588 | 0.702 |
| >= 0.129418 | 101 | 0.835 | 0.191 | 0.529 | 0.235 | 0.594 | 0.706 |
| >= 0.131441 | 100 | 0.835 | 0.175 | 0.529 | 0.216 | 0.600 | 0.710 |
| >= 0.132445 | 99 | 0.835 | 0.175 | 0.500 | 0.216 | 0.596 | 0.702 |
| >= 0.134423 | 98 | 0.835 | 0.175 | 0.471 | 0.216 | 0.602 | 0.707 |
| >= 0.141145 | 97 | 0.835 | 0.175 | 0.441 | 0.216 | 0.608 | 0.711 |
| >= 0.142049 | 96 | 0.835 | 0.159 | 0.441 | 0.196 | 0.615 | 0.715 |
| >= 0.142073 | 95 | 0.824 | 0.159 | 0.441 | 0.196 | 0.621 | 0.720 |
| >= 0.150577 | 94 | 0.812 | 0.159 | 0.441 | 0.196 | 0.617 | 0.712 |
| >= 0.151182 | 93 | 0.800 | 0.159 | 0.441 | 0.196 | 0.613 | 0.704 |
| >= 0.151571 | 92 | 0.800 | 0.159 | 0.412 | 0.196 | 0.620 | 0.708 |
| >= 0.152061 | 91 | 0.800 | 0.143 | 0.412 | 0.176 | 0.626 | 0.713 |
| >= 0.153376 | 90 | 0.788 | 0.143 | 0.412 | 0.176 | 0.622 | 0.704 |
| >= 0.154599 | 89 | 0.776 | 0.143 | 0.412 | 0.176 | 0.629 | 0.709 |
| >= 0.157635 | 88 | 0.776 | 0.143 | 0.412 | 0.157 | 0.636 | 0.713 |
| >= 0.160818 | 87 | 0.765 | 0.143 | 0.412 | 0.157 | 0.632 | 0.705 |
| >= 0.162543 | 86 | 0.753 | 0.143 | 0.412 | 0.157 | 0.628 | 0.697 |
| >= 0.163263 | 85 | 0.753 | 0.127 | 0.412 | 0.137 | 0.635 | 0.701 |
| >= 0.163295 | 84 | 0.741 | 0.127 | 0.412 | 0.137 | 0.631 | 0.693 |
| >= 0.164654 | 83 | 0.741 | 0.127 | 0.382 | 0.137 | 0.639 | 0.697 |
| >= 0.167880 | 82 | 0.741 | 0.111 | 0.382 | 0.118 | 0.646 | 0.702 |
| >= 0.171299 | 81 | 0.741 | 0.111 | 0.353 | 0.118 | 0.654 | 0.707 |
| >= 0.171686 | 80 | 0.741 | 0.095 | 0.353 | 0.098 | 0.662 | 0.711 |
| >= 0.174772 | 79 | 0.741 | 0.095 | 0.324 | 0.098 | 0.671 | 0.716 |
| >= 0.175964 | 78 | 0.729 | 0.095 | 0.324 | 0.098 | 0.679 | 0.721 |
| >= 0.176097 | 77 | 0.718 | 0.095 | 0.324 | 0.098 | 0.675 | 0.712 |
| >= 0.177243 | 76 | 0.706 | 0.095 | 0.324 | 0.098 | 0.671 | 0.703 |
| >= 0.177489 | 75 | 0.694 | 0.095 | 0.324 | 0.098 | 0.667 | 0.694 |
| >= 0.177668 | 74 | 0.694 | 0.095 | 0.294 | 0.098 | 0.676 | 0.699 |
| >= 0.179224 | 73 | 0.694 | 0.079 | 0.294 | 0.078 | 0.685 | 0.704 |
| >= 0.180491 | 72 | 0.682 | 0.079 | 0.294 | 0.078 | 0.681 | 0.695 |
| >= 0.182114 | 71 | 0.682 | 0.079 | 0.265 | 0.078 | 0.690 | 0.700 |
| >= 0.182434 | 70 | 0.671 | 0.079 | 0.265 | 0.078 | 0.686 | 0.691 |
| >= 0.188867 | 69 | 0.659 | 0.079 | 0.265 | 0.078 | 0.681 | 0.681 |
| >= 0.192047 | 68 | 0.647 | 0.079 | 0.265 | 0.078 | 0.676 | 0.671 |
| >= 0.192130 | 67 | 0.635 | 0.079 | 0.265 | 0.078 | 0.672 | 0.662 |
| >= 0.193633 | 66 | 0.624 | 0.079 | 0.265 | 0.078 | 0.667 | 0.652 |
| >= 0.195663 | 65 | 0.612 | 0.079 | 0.265 | 0.078 | 0.661 | 0.642 |
| >= 0.195865 | 64 | 0.600 | 0.079 | 0.265 | 0.078 | 0.656 | 0.632 |
| >= 0.196495 | 63 | 0.600 | 0.064 | 0.265 | 0.059 | 0.667 | 0.636 |
| >= 0.196830 | 62 | 0.588 | 0.064 | 0.265 | 0.059 | 0.661 | 0.626 |
| >= 0.199090 | 61 | 0.577 | 0.064 | 0.265 | 0.059 | 0.656 | 0.615 |
| >= 0.200004 | 60 | 0.577 | 0.064 | 0.235 | 0.059 | 0.667 | 0.620 |
| >= 0.200685 | 59 | 0.577 | 0.064 | 0.206 | 0.059 | 0.678 | 0.625 |
| >= 0.201465 | 58 | 0.565 | 0.064 | 0.206 | 0.059 | 0.672 | 0.614 |
| >= 0.202513 | 57 | 0.553 | 0.064 | 0.206 | 0.059 | 0.684 | 0.619 |
| >= 0.203753 | 56 | 0.541 | 0.064 | 0.206 | 0.059 | 0.696 | 0.624 |
| >= 0.204340 | 55 | 0.541 | 0.048 | 0.176 | 0.059 | 0.709 | 0.629 |
| >= 0.208967 | 54 | 0.529 | 0.048 | 0.176 | 0.059 | 0.704 | 0.618 |
| >= 0.211259 | 53 | 0.529 | 0.048 | 0.176 | 0.039 | 0.717 | 0.623 |
| >= 0.212171 | 52 | 0.518 | 0.048 | 0.176 | 0.039 | 0.712 | 0.612 |
| >= 0.217465 | 51 | 0.518 | 0.048 | 0.147 | 0.039 | 0.726 | 0.617 |
| >= 0.218300 | 50 | 0.506 | 0.048 | 0.147 | 0.039 | 0.720 | 0.605 |
| >= 0.218476 | 49 | 0.494 | 0.048 | 0.147 | 0.039 | 0.714 | 0.593 |
| >= 0.220745 | 48 | 0.482 | 0.048 | 0.147 | 0.039 | 0.708 | 0.581 |
| >= 0.221390 | 47 | 0.471 | 0.048 | 0.147 | 0.039 | 0.702 | 0.569 |
| >= 0.222997 | 46 | 0.459 | 0.048 | 0.147 | 0.039 | 0.696 | 0.556 |
| >= 0.223145 | 45 | 0.459 | 0.048 | 0.118 | 0.039 | 0.711 | 0.561 |
| >= 0.224698 | 44 | 0.459 | 0.048 | 0.088 | 0.039 | 0.727 | 0.566 |
| >= 0.225522 | 43 | 0.447 | 0.048 | 0.088 | 0.039 | 0.721 | 0.554 |
| >= 0.229031 | 42 | 0.435 | 0.048 | 0.088 | 0.039 | 0.714 | 0.540 |
| >= 0.231792 | 41 | 0.423 | 0.048 | 0.088 | 0.039 | 0.707 | 0.527 |
| >= 0.233416 | 40 | 0.423 | 0.048 | 0.059 | 0.039 | 0.725 | 0.532 |
| >= 0.235991 | 39 | 0.412 | 0.048 | 0.059 | 0.039 | 0.718 | 0.518 |
| >= 0.239365 | 38 | 0.412 | 0.032 | 0.059 | 0.020 | 0.737 | 0.523 |
| >= 0.240711 | 37 | 0.400 | 0.032 | 0.059 | 0.020 | 0.757 | 0.528 |
| >= 0.241893 | 36 | 0.388 | 0.032 | 0.059 | 0.020 | 0.778 | 0.533 |
| >= 0.241903 | 35 | 0.377 | 0.032 | 0.059 | 0.020 | 0.800 | 0.538 |
| >= 0.242388 | 34 | 0.365 | 0.032 | 0.059 | 0.020 | 0.794 | 0.524 |
| >= 0.245092 | 33 | 0.353 | 0.032 | 0.059 | 0.020 | 0.788 | 0.510 |
| >= 0.247221 | 32 | 0.341 | 0.032 | 0.059 | 0.020 | 0.781 | 0.495 |
| >= 0.253113 | 31 | 0.341 | 0.016 | 0.029 | 0.020 | 0.806 | 0.500 |
| >= 0.256921 | 30 | 0.329 | 0.016 | 0.029 | 0.020 | 0.800 | 0.485 |
| >= 0.257605 | 29 | 0.318 | 0.016 | 0.029 | 0.020 | 0.828 | 0.490 |
| >= 0.259039 | 28 | 0.306 | 0.016 | 0.029 | 0.020 | 0.821 | 0.474 |
| >= 0.259128 | 27 | 0.306 | 0.016 | 0.000 | 0.020 | 0.852 | 0.479 |
| >= 0.261240 | 26 | 0.294 | 0.016 | 0.000 | 0.020 | 0.846 | 0.463 |
| >= 0.261349 | 25 | 0.282 | 0.016 | 0.000 | 0.020 | 0.840 | 0.447 |
| >= 0.273102 | 24 | 0.271 | 0.016 | 0.000 | 0.020 | 0.833 | 0.430 |
| >= 0.274337 | 23 | 0.259 | 0.016 | 0.000 | 0.020 | 0.870 | 0.435 |
| >= 0.275170 | 22 | 0.247 | 0.016 | 0.000 | 0.020 | 0.864 | 0.418 |
| >= 0.283724 | 21 | 0.235 | 0.016 | 0.000 | 0.020 | 0.857 | 0.400 |
| >= 0.283947 | 20 | 0.235 | 0.000 | 0.000 | 0.000 | 0.900 | 0.405 |
| >= 0.288574 | 19 | 0.224 | 0.000 | 0.000 | 0.000 | 0.895 | 0.386 |
| >= 0.291126 | 18 | 0.212 | 0.000 | 0.000 | 0.000 | 0.889 | 0.368 |
| >= 0.291963 | 17 | 0.200 | 0.000 | 0.000 | 0.000 | 0.941 | 0.372 |
| >= 0.292134 | 16 | 0.188 | 0.000 | 0.000 | 0.000 | 0.938 | 0.353 |
| >= 0.293537 | 15 | 0.176 | 0.000 | 0.000 | 0.000 | 0.933 | 0.333 |
| >= 0.301016 | 14 | 0.165 | 0.000 | 0.000 | 0.000 | 0.929 | 0.313 |
| >= 0.302056 | 13 | 0.153 | 0.000 | 0.000 | 0.000 | 1.000 | 0.317 |
| >= 0.303614 | 12 | 0.141 | 0.000 | 0.000 | 0.000 | 1.000 | 0.296 |
| >= 0.308781 | 11 | 0.129 | 0.000 | 0.000 | 0.000 | 1.000 | 0.275 |
| >= 0.315314 | 10 | 0.118 | 0.000 | 0.000 | 0.000 | 1.000 | 0.253 |
| >= 0.324881 | 9 | 0.106 | 0.000 | 0.000 | 0.000 | 1.000 | 0.231 |
| >= 0.365954 | 8 | 0.094 | 0.000 | 0.000 | 0.000 | 1.000 | 0.208 |
| >= 0.369194 | 7 | 0.082 | 0.000 | 0.000 | 0.000 | 1.000 | 0.184 |
| >= 0.385931 | 6 | 0.071 | 0.000 | 0.000 | 0.000 | 1.000 | 0.160 |
| >= 0.395948 | 5 | 0.059 | 0.000 | 0.000 | 0.000 | 1.000 | 0.135 |
| >= 0.430890 | 4 | 0.047 | 0.000 | 0.000 | 0.000 | 1.000 | 0.110 |
| >= 0.454577 | 3 | 0.035 | 0.000 | 0.000 | 0.000 | 1.000 | 0.083 |
| >= 0.487942 | 2 | 0.024 | 0.000 | 0.000 | 0.000 | 1.000 | 0.056 |
| >= 0.625750 | 1 | 0.012 | 0.000 | 0.000 | 0.000 | 1.000 | 0.029 |

Full curve (170 rows) in `m1_results.json` → `b1.curve`.

## Per-band recall at the selected threshold

| band | recall |
|---|---|
| ambiguous | 0.324 |
| should-match | 0.729 |
| should-not-match | 0.098 |

## Agreement (two passes, agent-labeled)

- disagreement rate: **21/170 (0.1235)**
- ambiguous: 0.235 (8/34)
- should-match: 0.141 (12/85)
- should-not-match: 0.020 (1/51)
- flags: {'disagreed-downgraded': 14, 'disagreed-upgraded': 7}
- honesty clause: inter-pass disagreement is agent self-consistency under frozen rules (PROTOCOL v1.1), NOT human-human agreement

## B0 oracle

- rule: same `subflow` ⇒ pool (ABCD ground-truth ceiling within a subflow; trivially 1.0 inside the should-match band by construction).
- recall_sm = 1.000 · FFR = 0.048 · F1 = 0.883 · n_pooled = 85
- per-band recall: ambiguous=0.000, should-match=1.000, should-not-match=0.000

## Findings from the join (round 1, oversight re-derivation)

### F1 — the false-friend danger is INSIDE the flow, not across it

FFR split of the gold-`unrelated` class (63 = 15 same-flow + 48 diff-flow):

| threshold | FFR total | FFR same-flow (15) | FFR diff-flow (48) | cross-flow (18) | cross-product (9) | other-diff-flow (21) |
|---|---|---|---|---|---|---|
| >= 0.196495 | 4/63 = 0.064 | 2/15 = 0.133 | 2/48 = 0.042 | 1/18 = 0.056 | 1/9 = 0.111 | 0/21 = 0.000 |
| >= 0.171686 | 6/63 = 0.095 | 2/15 = 0.133 | 4/48 = 0.083 | 2/18 = 0.111 | 1/9 = 0.111 | 1/21 = 0.048 |

At `>= 0.171686` the same-flow FFR (13.3%, 2/15) is **higher** than the cross-flow FFR (11.1%, 2/18); at `>= 0.196495` the same-flow FFR (13.3%) is more than double the cross-flow FFR (5.6%). The same-flow bad pairs at both thresholds are the same two: **m1-0089, m1-0119** — both `subscription_inquiry` pairs whose convos sit in different subflows but share bill-management vocabulary (amount / pay / due / dispute wording). Cross-flow bad pairs at `>= 0.171686`: m1-0123, m1-0139.

**This inverts the method doc §5 expectation table**, which predicted cross-flow / cross-product would be the hard false-friend slice. It is not — on this data the hard slice is *within* a flow, between adjacent subflows that share product/bill vocabulary. **Implication for the sharing scope (commission §8.1):** the §M1 escape clause ("no method keeps the cross-flow FFR ≤ 10% ⇒ sharing is constrained to vertical/flow") does NOT fire — cross-flow FFR stays inside the bar at every passing threshold. But the data does not license global sharing either: the measured danger is *intra-flow, inter-subflow* pooling on shared vocabulary, so a sharing scope that pools across subflows inside a flow carries the same false-friend cost as cross-flow pooling. The scope decision needs sub-flow-level evidence, which this round does not settle (see F2). Honesty clause: all of this rests on an AGENT-LABELED gold set — inter-pass disagreement 21/170 = 0.1235 is a labeler self-consistency floor, not human inter-rater agreement.

### F2 — cross-flow "same problem" was never tested

All 69 gold same-problem pairs are same-flow (10 distinct flows: account_access, manage_account, order_issue, product_defect, purchase_dispute, shipping_issue, single_item_query, storewide_query, subscription_inquiry, troubleshoot_site); the gold set contains **zero** cross-flow and zero cross-product same-problem pairs. The cross-vertical reuse question is therefore **UNTESTED, not refuted** — recall across flows is unknown, not zero. This is a limitation of the gold set (its construction drew should-match only from same subflow). Do not read F1's inversion as evidence against cross-vertical sharing; it is silent on cross-flow *recall* by construction. Any sharing-scope claim from R1 must say so.

### F3 — the oracle label is not sufficient ground truth

Three pairs share a subflow (B0 pools them) yet the labeler called them **unrelated**, and B1 scores all three low:

| pair | subflow | B1 score |
|---|---|---|
| m1-0010 | manage | 0.0812 |
| m1-0038 | manage_cancel | 0.0970 |
| m1-0061 | manage_change_phone | 0.0553 |

B1 correctly refuses exactly the pairs the subflow oracle wrongly accepts. This is direct evidence for the method doc's own thesis — **intent match alone is not problem-shape match** — and it bounds B0 as a *ceiling on same-subflow coverage, not a definition of same-problem*. B0's FFR (4.8%, 3/63) is the FFR of *subflow identity*, not of problem shape.

Band-vs-canonical census: **18/170** canonical labels contradict the construction direction of their band (should-match labeled unrelated, ambiguous labeled unrelated, or should-not-match labeled related-but-different); 33 of 170 are off-center in total (the rest being 14 should-match pairs labeled related-but-different and 1 ambiguous pair labeled same-problem). The band is construction metadata, the label is the gold; every metric in this report follows the label.

## Closure line (round 1, R1 / BON-41)

**CONFIRMED** — independently re-derived from `b1_scores.jsonl` (PR #17, sha256:16 `9fe3e4b3c0978e1f`) joined to `gold_m1_pairs_agentlabeled.jsonl` (PR #18, sha256:16 `792df7d24fc0609a`) on pair_id (170/170, 0 only-onesided), no computation reused from either report. B1 (TF-IDF cosine, customer turns) at threshold 0.1965 (exact unique score 0.196495): **FFR 6.3% (4/63) at recall_sm 60.0%** → **PASS** of the frozen bar (≤10% at ≥60%). Best operating point (argmax pairwise-F1 in the pass region): threshold 0.175964 → recall_sm 72.9%, FFR 9.5% (6/63), F1 0.721; the max-recall point inside the pass region is 0.171686 → recall_sm 74.1% (76.8% of gold same-problem), FFR 9.5%. B0 oracle: recall_sm 100% at FFR 4.8% (3/63). Bar-passing thresholds: 18 (0.171686 → 0.196495). Per method doc §M1, B1 passing means B2 is **DROPPED** and the finding is *problem shape is lexical on this data*. HONESTY CLAUSE (attached to every 6.3%): the gold set is AGENT-LABELED; inter-pass disagreement 21/170 = 0.1235 is a labeler self-consistency floor, not human inter-rater agreement.

## B2

- status: dropped — B1 passed the bar (lexical finding).
