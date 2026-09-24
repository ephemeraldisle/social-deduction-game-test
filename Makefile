.PHONY: test
test:
	python3 -m unittest tests.test_game_smoke tests.test_browser -q
	node --test tests/test_current_ui.cjs
