;; -*- lexical-binding: t; -*-

(TeX-add-style-hook
 "reproducing_results"
 (lambda ()
   (LaTeX-add-labels
    "tab:study-population-counts"
    "tab:study-population-prescription-decisions"))
 :latex)

