;; -*- lexical-binding: t; -*-

(TeX-add-style-hook
 "main"
 (lambda ()
   (TeX-add-to-alist 'LaTeX-provided-class-options
                     '(("article" "10pt" "")))
   (TeX-add-to-alist 'LaTeX-provided-package-options
                     '(("xcolor" "table") ("amsmath" "") ("amssymb" "") ("iftex" "") ("fontenc" "T1") ("inputenc" "utf8") ("textcomp" "") ("unicode-math" "") ("lmodern" "") ("upquote" "") ("microtype" "") ("parskip" "") ("longtable" "") ("booktabs" "") ("array" "") ("calc" "") ("etoolbox" "") ("footnotehyper" "") ("footnote" "") ("graphicx" "") ("rxp_report" "") ("pdflscape" "") ("fancyhdr" "") ("draftwatermark" "") ("etoc" "") ("bookmark" "") ("xurl" "")))
   (TeX-run-style-hooks
    "latex2e"
    "appendix/reproducing_results"
    "appendix/financial_opportunity"
    "appendix/study_population_analysis"
    "appendix/entity_upload_analysis"
    "appendix/approval_analysis"
    "article"
    "art10"
    "xcolor"
    "amsmath"
    "amssymb"
    "iftex"
    "fontenc"
    "inputenc"
    "textcomp"
    "unicode-math"
    "lmodern"
    "upquote"
    "microtype"
    "parskip"
    "longtable"
    "booktabs"
    "array"
    "calc"
    "etoolbox"
    "footnotehyper"
    "footnote"
    "graphicx"
    "rxp_report"
    "pdflscape"
    "fancyhdr"
    "draftwatermark"
    "etoc"
    "bookmark"
    "xurl")
   (TeX-add-symbols
    '("pandocbounded" 1)
    "tightlist")
   (LaTeX-add-labels
    "abstract"
    "appendix"
    "references"
    "ref:analysis-repository")
   (LaTeX-add-pagestyles
    "report")
   (LaTeX-add-counters
    "none")
   (LaTeX-add-saveboxes
    "pandoc"))
 :latex)

