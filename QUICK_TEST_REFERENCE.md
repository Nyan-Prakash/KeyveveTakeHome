# Quick Test Command Reference 🚀

## Essential Commands

### Activate Environment (Required First!)
```bash
source venv/bin/activate
```

### Run All Verified Passing Tests (24 tests)
```bash
python -m pytest tests/unit/test_selector.py tests/unit/test_budget_verification.py tests/eval/test_pr6_happy_path.py tests/eval/test_eval_runner.py -v
```

### Run by Category
```bash
# Selector tests (11) - All passing ✅
python -m pytest tests/unit/test_selector.py -v

# PR6 eval tests (7) - All passing ✅  
python -m pytest tests/eval/test_pr6_happy_path.py -v

# Eval runner (5) - All passing ✅
python -m pytest tests/eval/test_eval_runner.py -v

# Budget test (1) - Passing ✅
python -m pytest tests/unit/test_budget_verification.py -v
```

### Quick Single Test
```bash
# Run one specific test
python -m pytest tests/unit/test_selector.py::TestSelectorScoring::test_score_ordering -v
```

## Expected Results

```
======================== 24 passed in X.XXs ========================
```

All 24 tests should pass! ✅

## Need Help?

- See `RUN_TESTS.md` for detailed guide
- See `TEST_FIXES_COMPLETE.md` for what was fixed
- See `TEST_FIX_SUMMARY.md` for technical details

## Troubleshooting One-Liners

```bash
# Forgot to activate venv?
source venv/bin/activate

# Dependencies not installed?
pip install -r requirements.txt

# Want to see test names?
python -m pytest --collect-only tests/unit/test_selector.py
```

---
**Remember**: Always run tests with `source venv/bin/activate` first! 🐍
