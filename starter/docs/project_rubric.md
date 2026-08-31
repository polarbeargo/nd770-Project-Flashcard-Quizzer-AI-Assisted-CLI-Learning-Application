# Rubric: AI-Assisted Development Project

## Starter Code

Starter code contains:

- **main.py** - Entry point demonstrating basic application structure and development patterns
- **utils/** - Core utility modules including `task_manager.py` and `file_handler.py` with basic CRUD operations
- **tests/** - Unit test suite demonstrating proper testing practices for AI-assisted development
- **docs/** - Documentation templates including AI interaction logging, design patterns guide, and final report template
- **ai_guidance/** - Best practices for AI prompting and systematic code review checklists
- **.claude/** - Configuration files for AI assistant integration (principles apply to any AI tool)

## Section 1: AI Collaboration and Code Review

| **Criteria** | **Submission Requirements** | **Reviewer Tips** |
|----------|------------------------|---------------|
| **AI Code Review** | - Use AI tools to generate code for your application<br>- Review all AI-generated code using the provided checklist<br>- Document your review process in `ai_edit_log.md` with specific examples<br>- Show evidence of modifying or rejecting poor AI suggestions | - Check that students actually reviewed AI code rather than blindly accepting it<br>- Look for specific examples of code improvements or rejections<br>- Verify that `ai_edit_log.md` contains meaningful analysis, not just timestamps<br>- Ensure students can explain why they accepted or rejected AI suggestions |
| **Code Quality Standards** | - All code follows PEP 8 style guidelines<br>- Proper error handling and input validation<br>- Code is readable and maintainable<br>- Functions have appropriate docstrings | - Run `black`, `flake8`, and `mypy` to verify code quality<br>- Check for descriptive variable names and clear function signatures<br>- Verify error handling covers edge cases<br>- Ensure docstrings are present and informative |

## Section 2: Application Development

| **Criteria** | **Submission Requirements** | **Reviewer Tips** |
|----------|------------------------|---------------|
| **Functional Application** | - Build a working application that extends the starter code<br>- Implement at least 3 new features beyond basic CRUD operations<br>- Application should have clear functionality and purpose<br>- Use AI assistance throughout the development process | - Test the application to ensure it works as intended<br>- Verify new features integrate well with existing code<br>- Check that the application has a clear scope and purpose<br>- Look for evidence of AI assistance in code generation |
| **Design Patterns** | - Implement at least 1 design pattern from the provided guide<br>- Pattern should serve a real purpose, not be forced<br>- Document why you chose the pattern in your final report | - Verify the pattern is implemented correctly<br>- Check that the pattern improves code maintainability<br>- Ensure pattern isn't over-engineered for the problem<br>- Look for clear explanation of pattern choice |

## Section 3: Testing and Quality Assurance

| **Criteria** | **Submission Requirements** | **Reviewer Tips** |
|----------|------------------------|---------------|
| **Unit Testing** | - Achieve >80% test coverage using pytest<br>- Write tests for both original and AI-generated code<br>- Include tests for edge cases and error conditions<br>- Use clear test names that describe what is being tested | - Run `pytest --cov=. --cov-report=html` to verify coverage<br>- Check that tests cover happy path, edge cases, and error conditions<br>- Verify tests are meaningful and not just coverage-driven<br>- Ensure test names clearly describe the scenario being tested |
| **AI-Generated Code Validation** | - Test all AI-generated code thoroughly<br>- Document any issues found with AI code in `ai_edit_log.md`<br>- Show evidence of fixing or rejecting problematic AI suggestions | - Look for evidence that students tested AI code rather than trusting it<br>- Check for documentation of AI code problems and how they were resolved<br>- Verify students understand they are responsible for all code quality |

## Section 4: Documentation and Communication

| **Criteria** | **Submission Requirements** | **Reviewer Tips** |
|----------|------------------------|---------------|
| **AI Interaction Log** | - Complete detailed `ai_edit_log.md` with specific examples of AI usage<br>- Document prompts you used and AI responses you received<br>- Explain your decision-making process for accepting/rejecting AI suggestions<br>- Include at least 5 meaningful AI interactions | - Look for specific examples of AI interactions, not just generic descriptions<br>- Verify students explained their reasoning behind decisions<br>- Check that log shows both successful and unsuccessful AI interactions<br>- Ensure entries demonstrate learning and improvement over time |
| **Final Report** | - Complete the final report using the provided template<br>- Explain how you used AI throughout your development process<br>- Reflect on what you learned about working with AI tools<br>- Report should be 1000-1500 words | - Check that all sections of the template are completed<br>- Look for thoughtful reflection on the AI collaboration experience<br>- Verify students can articulate lessons learned<br>- Ensure report demonstrates understanding of course concepts |
| **README Updates** | - Update README.md with new features and setup instructions<br>- Provide clear usage examples<br>- Document any dependencies or installation requirements | - Verify README accurately describes the current application<br>- Check that setup instructions are complete and accurate<br>- Ensure new features are properly documented |

## Suggestions to Make Your Project Stand Out

- **Implement multiple design patterns** that serve real purposes in your application
- **Create comprehensive test suite** with >90% coverage including edge cases
- **Add advanced features** like configuration management, logging, or data export capabilities
- **Write detailed AI interaction analysis** showing sophisticated understanding of AI strengths and weaknesses
- **Implement security best practices** including input validation and error handling
- **Create professional documentation** that would help other developers understand your AI collaboration process
- **Add performance optimizations** and document your decision-making process
- **Include integration with external APIs** or services using AI assistance
- **Develop custom utilities** or helper functions that extend the starter code meaningfully
- **Create visual documentation** like diagrams or flowcharts explaining your application architecture

## General Reviewer Best Practices

- **Check AI Collaboration**: Verify that students actually used AI tools and documented their process
- **Test the Application**: Run the code and test various scenarios including edge cases
- **Review Code Quality**: Use automated tools (`black`, `flake8`, `mypy`, `pytest`) to verify standards
- **Validate Documentation**: Ensure AI interaction logs show meaningful analysis, not just timestamps
- **Look for Critical Thinking**: Students should demonstrate they reviewed AI suggestions rather than blindly accepting them
- **Assess Learning**: Check that students can explain what they learned about working with AI tools
- **Verify Functionality**: Ensure the application works correctly and meets the stated requirements

## Submission Requirements

- **Complete codebase** with all source files, tests, and documentation
- **Completed `ai_edit_log.md`** with at least 5 detailed AI interaction examples
- **Final project report** using the provided template (1000-1500 words)
- **Updated README.md** with current setup instructions and feature descriptions
- **Test coverage report** demonstrating >80% coverage
- **Code quality verification** (all linting tools should pass without errors)

> **Note:** Students can use any AI coding assistant (Claude, ChatGPT, GitHub Copilot, etc.). The principles and assessment criteria apply to all tools.

---

**Remember**: The goal is to demonstrate that you can work effectively with AI tools while maintaining high engineering standards. Focus on quality code, thorough testing, and thoughtful documentation of your AI collaboration process.
