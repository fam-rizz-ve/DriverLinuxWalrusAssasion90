.PHONY: install uninstall status logs restart stop test clean help

help:
	@echo "Walrus Assassin 90 LCD Driver"
	@echo ""
	@echo "Targets:"
	@echo "  make install    - Install driver, udev rule, and systemd service"
	@echo "  make uninstall  - Remove driver and all configuration"
	@echo "  make status     - Show service status"
	@echo "  make logs       - Follow service logs (Ctrl-C to exit)"
	@echo "  make restart    - Restart the service"
	@echo "  make stop       - Stop the service"
	@echo "  make test       - Run driver in foreground with debug output"
	@echo "  make clean      - Remove venv and cache files"

install:
	@bash install.sh

uninstall:
	@bash uninstall.sh

status:
	@systemctl --user status cooler-lcd.service

logs:
	@journalctl --user -u cooler-lcd.service -f

restart:
	@systemctl --user restart cooler-lcd.service

stop:
	@systemctl --user stop cooler-lcd.service

test:
	@python3 src/walrus_lcd.py --print

clean:
	@rm -rf venv __pycache__ .pytest_cache
	@echo "Cleaned."
