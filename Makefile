test:
	PYTHONPATH=. python3 -m pytest tests/ -v

install-hooks:
	@for hook in hooks/*; do \
		name=$$(basename "$$hook"); \
		ln -sf ../../$$hook .git/hooks/$$name; \
		chmod +x $$hook; \
		echo "Installed $$name hook"; \
	done
