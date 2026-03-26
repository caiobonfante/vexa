ZOOM_DATA := ../../data/raw

.PHONY: score score-latest

# Score the zoom-3sp-basic dataset
score:
	python3 score-zoom.py $(ZOOM_DATA)/zoom-3sp-basic

# Score the most recent zoom dataset (by modification time)
score-latest:
	python3 score-zoom.py $$(ls -td $(ZOOM_DATA)/zoom-* 2>/dev/null | head -1)
