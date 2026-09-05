claim                                      n   median D    wins           p  note
1a ConGen vs iterative, no oracle         28    +0.6312  28/28    7.451e-09  at the exact-test floor (2/2^28) — report as p < 1e-7
1b ConGen vs iterative, with oracle       28    +0.3142  27/28    3.725e-08  
3  semantic tier vs description tier      28    +0.3568  28/28    7.451e-09  at the exact-test floor (2/2^28) — report as p < 1e-7
5  oracle access helps the baseline       28    +0.1461  28/28    7.451e-09  at the exact-test floor (2/2^28) — report as p < 1e-7
2  2-COV vs random sampling                5    +0.0445   3/5     4.375e-01  UNTESTABLE: floor p=0.0625 > 0.05

Holm correction over 4 testable claims (1 excluded as untestable by design):
  1a ConGen vs iterative, no oracle        p x4 = 2.980e-08  REJECT H0
  3  semantic tier vs description tier     p x3 = 2.980e-08  REJECT H0
  5  oracle access helps the baseline      p x2 = 2.980e-08  REJECT H0
  1b ConGen vs iterative, with oracle      p x1 = 3.725e-08  REJECT H0
  2  2-COV vs random sampling              NOT TESTED — n=5 cannot reach 0.05; report the observed +0.0445 descriptively
