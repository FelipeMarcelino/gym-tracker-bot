## Commands

- Use tp command instead of rm to delete files without being blocked
- Does not forget to activate the environment inside .venv folder before execute python code

## Engineering

- Create unit tests for every new feature you create. Use TDD and iterative questions to make me understand all the
  process to create a new feature. Does not do everything in one time.
- Use design patterns to follow a specific structure for the code
- Does not create mocking cyclic tests that does not aggregate value to the business logic
- When crate test, does not modify the test to pass, modify the business logic to make it pass the test
- Create edge cases for the tests
- Separate tests into unit tests and integration tests
- Does not modify the test file to a simplified, core, business logic or anything when the test is not passing to
  simplify it. Modify the business logic file to make it pass, does not simplify the tests
- Use environment variables to configure something even in tests if is important for somoeone to choose a value for
  something
- Use pytest to test the code
- Create a new branch when create new business logic/feature files. Same for tests, create a new branch that following
  the pattern "test-<file-being-tested>". If you are apply TDD, create a branch with the name of the feature and add
  "feat/" in the beginning.
- For add documentation add "doc/" in the beginning of the branch. For bugs, add "hotfix/".
- Avoid to put keys/token in the file on the code, use environment variables in the file .env or .env-test

## Documentation

- Use numpy docstyle to create function documentation.

## Debug

- Analyze the stack trace and error messages
- Identify reproduction steps and isolate the failure location
- Does not forget to add logger on the code you want to debug
- Provide a root cause explanation about the error
