# All aged-order contact timing: daily-bins

CMPU vet-diet CUSTOMER_UPLOAD first-order cohort; every aged order, regardless of reordering. Distinct order/order-line keys collapse shipment rows; orders are counted once across prescriptions and lines. All available HANDLED_FLAG=TRUE contact rows on aged orders, all categories, with no contact-time restriction. Contacts and cancellations are UTC. The as-of cutoff applies to cancellations, not contact history. Lag = contact time minus cancellation; exact nanosecond floor bins [day,day+1). Undated contacts remain in details and totals but are excluded from histogram shares. Counts follow contact source rows (contact legs), not unique sessions. Daily customer/session/order counts can overlap across bins. Full data are in the corresponding data/ Parquet files. Source extracted 2026-10-27T20:26:14.162146+00:00; SHA-256 5001100ecaaac06e0c82ac13cc26031e6168ebfcab923295726b6596d26e657c.

| relative_day | contact_legs | orders | customers | distinct_sessions | share_of_dated_contacts | upper_day | timing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| -14 | 36.0 | 35.0 | 35.0 | 36.0 | 0.001143692219715983 | -13 | Before cancellation |
| -13 | 2280.0 | 2252.0 | 2219.0 | 2278.0 | 0.07243384058201226 | -12 | Before cancellation |
| -12 | 1768.0 | 1670.0 | 1652.0 | 1754.0 | 0.05616799567938495 | -11 | Before cancellation |
| -11 | 15400.0 | 14227.0 | 12644.0 | 15356.0 | 0.4892461162118372 | -10 | Before cancellation |
| -10 | 8396.0 | 7816.0 | 7034.0 | 8367.0 | 0.2667344410204276 | -9 | Before cancellation |
| -9 | 1655.0 | 1533.0 | 1518.0 | 1643.0 | 0.05257807287860978 | -8 | Before cancellation |
| -8 | 674.0 | 625.0 | 623.0 | 663.0 | 0.02141245989134924 | -7 | Before cancellation |
| -7 | 147.0 | 120.0 | 120.0 | 139.0 | 0.004670076563840264 | -6 | Before cancellation |
| -6 | 109.0 | 81.0 | 80.0 | 98.0 | 0.0034628458874733934 | -5 | Before cancellation |
| -5 | 81.0 | 60.0 | 60.0 | 73.0 | 0.002573307494360962 | -4 | Before cancellation |
| -4 | 94.0 | 71.0 | 71.0 | 84.0 | 0.0029863074625917337 | -3 | Before cancellation |
| -3 | 124.0 | 101.0 | 101.0 | 117.0 | 0.003939384312355053 | -2 | Before cancellation |
| -2 | 148.0 | 134.0 | 134.0 | 142.0 | 0.0047018457921657085 | -1 | Before cancellation |
| -1 | 294.0 | 213.0 | 213.0 | 269.0 | 0.009340153127680528 | 0 | Before cancellation |
| 0 | 66.0 | 46.0 | 46.0 | 54.0 | 0.002096769069479302 | 1 | At/after cancellation |
| 1 | 24.0 | 16.0 | 16.0 | 19.0 | 0.0007624614798106554 | 2 | At/after cancellation |
| 2 | 32.0 | 19.0 | 19.0 | 25.0 | 0.0010166153064142072 | 3 | At/after cancellation |
| 3 | 21.0 | 12.0 | 12.0 | 15.0 | 0.0006671537948343234 | 4 | At/after cancellation |
| 4 | 22.0 | 11.0 | 11.0 | 16.0 | 0.0006989230231597675 | 5 | At/after cancellation |
| 5 | 11.0 | 9.0 | 9.0 | 10.0 | 0.00034946151157988373 | 6 | At/after cancellation |
| 6 | 11.0 | 7.0 | 7.0 | 11.0 | 0.00034946151157988373 | 7 | At/after cancellation |
| 7 | 12.0 | 6.0 | 6.0 | 11.0 | 0.0003812307399053277 | 8 | At/after cancellation |
| 8 | 7.0 | 4.0 | 4.0 | 4.0 | 0.00022238459827810783 | 9 | At/after cancellation |
| 9 | 4.0 | 3.0 | 3.0 | 4.0 | 0.0001270769133017759 | 10 | At/after cancellation |
| 10 | 4.0 | 3.0 | 3.0 | 3.0 | 0.0001270769133017759 | 11 | At/after cancellation |
| 11 | 12.0 | 6.0 | 6.0 | 10.0 | 0.0003812307399053277 | 12 | At/after cancellation |
| 12 | 3.0 | 1.0 | 1.0 | 2.0 | 9.530768497633192e-05 | 13 | At/after cancellation |
| 13 | 4.0 | 3.0 | 3.0 | 3.0 | 0.0001270769133017759 | 14 | At/after cancellation |
| 14 | 6.0 | 3.0 | 3.0 | 5.0 | 0.00019061536995266384 | 15 | At/after cancellation |
| 15 | 6.0 | 3.0 | 3.0 | 5.0 | 0.00019061536995266384 | 16 | At/after cancellation |
| 16 | 1.0 | 1.0 | 1.0 | 1.0 | 3.1769228325443974e-05 | 17 | At/after cancellation |
| 17 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 18 | At/after cancellation |
| 18 | 5.0 | 2.0 | 2.0 | 4.0 | 0.00015884614162721988 | 19 | At/after cancellation |
| 19 | 1.0 | 1.0 | 1.0 | 1.0 | 3.1769228325443974e-05 | 20 | At/after cancellation |
| 20 | 2.0 | 2.0 | 2.0 | 2.0 | 6.353845665088795e-05 | 21 | At/after cancellation |
| 21 | 2.0 | 1.0 | 1.0 | 1.0 | 6.353845665088795e-05 | 22 | At/after cancellation |
| 22 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 23 | At/after cancellation |
| 23 | 7.0 | 2.0 | 2.0 | 6.0 | 0.00022238459827810783 | 24 | At/after cancellation |
| 24 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 25 | At/after cancellation |
| 25 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 26 | At/after cancellation |
| 26 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 27 | At/after cancellation |
| 27 | 1.0 | 1.0 | 1.0 | 1.0 | 3.1769228325443974e-05 | 28 | At/after cancellation |
| 28 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 29 | At/after cancellation |
| 29 | 2.0 | 1.0 | 1.0 | 1.0 | 6.353845665088795e-05 | 30 | At/after cancellation |
| 30 | 1.0 | 1.0 | 1.0 | 1.0 | 3.1769228325443974e-05 | 31 | At/after cancellation |
| 31 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 32 | At/after cancellation |
| 32 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 33 | At/after cancellation |
| 33 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 34 | At/after cancellation |
| 34 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 35 | At/after cancellation |
| 35 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 36 | At/after cancellation |
| 36 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 37 | At/after cancellation |
| 37 | 2.0 | 1.0 | 1.0 | 1.0 | 6.353845665088795e-05 | 38 | At/after cancellation |
| 38 | 1.0 | 1.0 | 1.0 | 1.0 | 3.1769228325443974e-05 | 39 | At/after cancellation |
| 39 | 1.0 | 1.0 | 1.0 | 1.0 | 3.1769228325443974e-05 | 40 | At/after cancellation |
