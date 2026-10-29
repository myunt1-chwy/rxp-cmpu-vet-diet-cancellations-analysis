;; -*- lexical-binding: t; -*-

(TeX-add-style-hook
 "study_population_analysis"
 (lambda ()
   (TeX-run-style-hooks
    "appendix/survival_analysis"
    "appendix/entity_upload_analysis"
    "appendix/approval_analysis")
   (LaTeX-add-labels
    "app:aged-order-analysis"
    "tab:study-population-counts"
    "tab:study-population-prescription-decisions"
    "tab:first-all-order-cancellations"
    "fig:first-order-lines-customer-upload"))
 :latex)

