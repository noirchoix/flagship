PROMPT_PATTERNS_DETAILED = [
    {
        "pattern_name": "Alternative Approaches",
        "pattern_family": "exploration_and_comparison",
        "primary_purpose": (
            "Surface multiple viable ways to accomplish a task or solve a problem and "
            "compare them so the user can choose among them."
        ),
        "core_mechanism": (
            "Given a description of a task or problem X, the model lists several alternative "
            "approaches to achieving X. It can optionally include the originally implied "
            "approach, compare pros and cons across options, and ask the user which approach "
            "to follow next."
        ),
        "input_fields": [
            {
                "name": "task_X_description",
                "description": "Natural-language description of the user’s task or problem.",
                "required": True
            },
            {
                "name": "include_original_approach_bool",
                "description": (
                    "If true, the model also describes the approach implied by the user’s "
                    "initial request and includes it in the comparison."
                ),
                "required": False
            },
            {
                "name": "compare_contrast_bool",
                "description": (
                    "If true, the model compares pros and cons of each alternative approach."
                ),
                "required": False
            },
            {
                "name": "ask_user_to_choose_bool",
                "description": (
                    "If true, the model ends by asking the user which approach to follow."
                ),
                "required": False
            }
        ],
        "output_fields": [
            {
                "name": "approach_list",
                "description": "List of named alternative approaches for accomplishing X."
            },
            {
                "name": "comparison_table",
                "description": (
                    "Optional structured comparison (pros / cons / conditions) between approaches."
                )
            },
            {
                "name": "follow_up_question",
                "description": (
                    "Optional question that asks the user to select an approach or refine their goal."
                )
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "problem_restatement",
                    "description": "Restate or clarify the task X in neutral language."
                },
                {
                    "name": "approach_generation",
                    "description": "Generate several distinct solution strategies for X."
                },
                {
                    "name": "comparison",
                    "description": "Compare approaches on criteria such as cost, speed, risk, quality."
                },
                {
                    "name": "selection_prompt",
                    "description": "Optionally prompt the user to pick an approach or combination."
                }
            ]
        },
        "control_flags": {
            "max_approaches": "Maximum number of approaches to list (e.g. 3–7).",
            "require_diversity": "If true, discourage near-duplicate approaches.",
            "include_original_approach": "Whether to model the approach implied by the initial request.",
            "include_comparison": "Whether to add a structured comparison section."
        },
        "typical_use_cases": [
            "Prompt engineering and rewording tasks.",
            "Design and architecture brainstorming.",
            "Choosing between modeling or implementation strategies.",
            "Exploring alternative plans for a project."
        ],
        "risks_and_misuses": [
            "Too many low-quality approaches that overwhelm the user.",
            "Superficial comparisons that overstate differences.",
            "Model hallucinating approaches that are not actually feasible."
        ],
        "example_prompt_skeleton": (
            "You are an expert assistant. I will describe a task.\n\n"
            "Task: {task_X_description}\n\n"
            "1. List {N} distinct, high-quality approaches to accomplishing this task.\n"
            "{% if include_original_approach_bool %}"
            "   Include the approach implied by my original request as one of the options.\n"
            "{% endif %}"
            "{% if compare_contrast_bool %}"
            "2. Compare the approaches in terms of advantages, disadvantages, and when each is "
            "most appropriate.\n"
            "{% endif %}"
            "{% if ask_user_to_choose_bool %}"
            "3. End by asking me which approach I would like to pursue next.\n"
            "{% endif %}"
        )
    },
    {
        "pattern_name": "Ask for Input",
        "pattern_family": "interaction_loop",
        "primary_purpose": (
            "Ensure the model explicitly requests a specific input from the user "
            "before starting its main behavior."
        ),
        "core_mechanism": (
            "The prompt defines a role or behavior for the model and instructs it to ask the user "
            "for a particular piece of input X (e.g., a document, question, list, or goal) "
            "before it begins performing that behavior. The model repeats this request whenever "
            "it needs a new instance of X."
        ),
        "input_fields": [
            {
                "name": "task_description",
                "description": (
                    "Description of the ongoing behavior the model should perform "
                    "once it has the required input."
                ),
                "required": True
            },
            {
                "name": "input_label_X",
                "description": (
                    "Name or description of the required input from the user "
                    "(e.g. 'email chain', 'text to translate', 'PDF')."
                ),
                "required": True
            }
        ],
        "output_fields": [
            {
                "name": "initial_input_request",
                "description": "Clear question asking the user to provide X before starting."
            },
            {
                "name": "loop_prompt",
                "description": (
                    "Standard phrasing used whenever another input X is needed "
                    "for the next cycle."
                )
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "role_declaration",
                    "description": "Model summarizes its function for the user."
                },
                {
                    "name": "first_input_request",
                    "description": "Model asks for the first instance of X."
                },
                {
                    "name": "process_input",
                    "description": (
                        "For each received X, the model applies the task behavior "
                        "and returns a result."
                    )
                },
                {
                    "name": "repeat_request",
                    "description": (
                        "After producing a result, the model asks for the next X or "
                        "whether to stop."
                    )
                }
            ]
        },
        "control_flags": {
            "require_confirmation": (
                "If true, the model confirms the task description before asking for input."
            ),
            "input_size_hint": "Optional guidance on the expected size/length of X.",
            "stop_keyword": "Optional keyword the user can send to terminate the loop."
        },
        "typical_use_cases": [
            "Iterative summarization of multiple emails or documents.",
            "Batch translation or paraphrasing.",
            "Stepwise troubleshooting where each step needs new information."
        ],
        "risks_and_misuses": [
            "Model may forget to ask for the next input and instead hallucinate it.",
            "Ambiguous description of X can confuse users about what to provide.",
            "If X can contain sensitive data, must be paired with privacy guidance."
        ],
        "example_prompt_skeleton": (
            "From now on, you will {task_description}.\n"
            "Before you start, ask me for the first {input_label_X}.\n"
            "After you finish processing each {input_label_X}, ask me if I want to process "
            "another one or stop."
        )
    },
    {
        "pattern_name": "Fact Check List",
        "pattern_family": "quality_control",
        "primary_purpose": (
            "Make the model enumerate key factual statements in its output that should be "
            "verified, improving transparency and enabling downstream fact-checking."
        ),
        "core_mechanism": (
            "Whenever the model generates content, it also produces a list of fundamental facts "
            "from that content. These facts are those whose incorrectness would significantly "
            "undermine the answer. The list is inserted at a specified position in the output "
            "such as the end."
        ),
        "input_fields": [
            {
                "name": "fact_list_position",
                "description": (
                    "Where to place the fact list (e.g. 'at the end', 'under a heading', "
                    "'in a separate section')."
                ),
                "required": True
            },
            {
                "name": "fact_granularity_hint",
                "description": (
                    "Optional guidance on how detailed the facts should be "
                    "(e.g. '5–10 bullet points')."
                ),
                "required": False
            }
        ],
        "output_fields": [
            {
                "name": "main_content",
                "description": "The primary answer, explanation, or summary."
            },
            {
                "name": "fact_check_list",
                "description": (
                    "A bullet list of core factual claims that should be externally verified."
                )
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "content_generation",
                    "description": "Model produces the main answer or narrative."
                },
                {
                    "name": "fact_extraction",
                    "description": (
                        "Model scans its own output and extracts key factual statements."
                    )
                },
                {
                    "name": "fact_list_formatting",
                    "description": (
                        "Model formats these facts as a list and inserts it at the "
                        "specified position."
                    )
                }
            ]
        },
        "control_flags": {
            "min_fact_count": "Minimum number of facts to list.",
            "max_fact_count": "Maximum number of facts to list.",
            "fact_style": "Required style for the facts (e.g. short sentences, bullet points)."
        },
        "typical_use_cases": [
            "Research article summaries that need external validation.",
            "Explanatory essays or reports prepared for decision makers.",
            "Any content that will be routed into an automated fact-checking pipeline."
        ],
        "risks_and_misuses": [
            "Model may miss important implicit assumptions that should also be checked.",
            "Low-quality fact lists that restate trivial points instead of key claims.",
            "Users may treat unverified facts as fully reliable."
        ],
        "example_prompt_skeleton": (
            "Write the requested answer or summary.\n\n"
            "Then, under the heading 'Key Facts to Verify', list {N} factual statements from "
            "your own output that are most critical to its correctness. Place this section "
            "{fact_list_position}."
        )
    },
    {
        "pattern_name": "Menu Actions",
        "pattern_family": "interaction_loop",
        "primary_purpose": (
            "Define a small command language where specific phrases from the user trigger "
            "well-defined actions by the model."
        ),
        "core_mechanism": (
            "The prompt enumerates a set of commands (strings) and their corresponding "
            "actions. Whenever the user types command X, the model executes the mapped action Y. "
            "After each response, the model asks the user what to do next, keeping the loop open."
        ),
        "input_fields": [
            {
                "name": "commands_and_actions",
                "description": (
                    "Mapping from user command phrases to the actions the model should take."
                ),
                "required": True
            },
            {
                "name": "final_prompt_for_next_action",
                "description": (
                    "Optional standard phrasing asking the user what to do next "
                    "after each action."
                ),
                "required": False
            }
        ],
        "output_fields": [
            {
                "name": "action_result",
                "description": "Result of executing the chosen action."
            },
            {
                "name": "next_action_prompt",
                "description": "Question prompting the user for the next command."
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "command_explanation",
                    "description": "Model lists the available commands and what each does."
                },
                {
                    "name": "command_execution",
                    "description": (
                        "For each user message, model matches it to a command and performs "
                        "the associated action."
                    )
                },
                {
                    "name": "loop_prompt",
                    "description": "Model asks for the user's next command."
                }
            ]
        },
        "control_flags": {
            "strict_command_matching": (
                "If true, act only when user input matches a known command exactly/closely."
            ),
            "allow_free_text": (
                "If true, allow the user to send natural language instead of commands and "
                "handle it gracefully."
            ),
            "show_help_command": "Optional command (e.g. 'help') to re-list available actions."
        },
        "typical_use_cases": [
            "Simple dashboards inside chat (e.g. project management commands).",
            "Interactive tools for editing, reviewing, or tagging content.",
            "Data exploration or note-taking with a small set of verbs."
        ],
        "risks_and_misuses": [
            "Ambiguity if user input partially matches several commands.",
            "Unexpected behavior if the model improvises commands that were not defined.",
            "User may forget available actions without periodic reminders."
        ],
        "example_prompt_skeleton": (
            "You support the following commands:\n"
            "{commands_and_actions}\n\n"
            "Whenever I type one of these commands, perform the described action and show me "
            "the result. At the end of each response, say:\n"
            "\"What would you like to do next?\""
        )
    },
    {
        "pattern_name": "Meta Language Creation",
        "pattern_family": "meta_language",
        "primary_purpose": (
            "Create a custom shorthand or symbolic language where special tokens map to "
            "longer meanings, actions, or structures."
        ),
        "core_mechanism": (
            "The prompt defines one or more meta-tokens (e.g. functions, tags, markers) and "
            "specifies what each should mean. The model interprets any future appearance of "
            "these tokens according to these definitions when generating or parsing text."
        ),
        "input_fields": [
            {
                "name": "meta_phrases_mapping",
                "description": (
                    "Mapping from meta tokens (e.g. 'variations(x)', 'Task X [Task Y]') to "
                    "their intended meanings or operations."
                ),
                "required": True
            },
            {
                "name": "scope_of_meta_language",
                "description": (
                    "Where the meta-language applies (all messages, only user messages, only "
                    "model outputs, or both)."
                ),
                "required": False
            }
        ],
        "output_fields": [
            {
                "name": "interpreted_output",
                "description": (
                    "Model output that applies the meta-language rules to expand or act upon "
                    "the meta tokens."
                )
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "definition_phase",
                    "description": "Define each meta token and its meaning."
                },
                {
                    "name": "usage_phase",
                    "description": (
                        "User and model begin using the meta tokens in dialogue or commands."
                    )
                },
                {
                    "name": "resolution_phase",
                    "description": (
                        "Model resolves meta tokens into their full meanings during generation."
                    )
                }
            ]
        },
        "control_flags": {
            "allow_new_tokens": "Whether new meta tokens can be introduced dynamically.",
            "expand_inline": (
                "If true, expand meta tokens directly in output; otherwise, explain them."
            )
        },
        "typical_use_cases": [
            "Custom prompt DSLs for power users.",
            "Concise task specification in technical or research workflows.",
            "Graph or dependency notations for project management."
        ],
        "risks_and_misuses": [
            "User confusion if token meanings are not documented or remembered.",
            "Model misinterpreting similar natural-language strings as meta tokens.",
            "Meta language collisions across different sessions or tools."
        ],
        "example_prompt_skeleton": (
            "We are going to define a small meta-language.\n"
            "Here are the meta tokens and what they mean:\n"
            "{meta_phrases_mapping}\n\n"
            "From now on, whenever I use one of these tokens, interpret it according to its "
            "definition and respond accordingly."
        )
    },
    {
        "pattern_name": "Recipe Pattern",
        "pattern_family": "planning_and_decomposition",
        "primary_purpose": (
            "Turn a high-level goal, plus a few known steps, into a complete, ordered plan."
        ),
        "core_mechanism": (
            "Given a goal X and a partial list of steps known by the user, the model constructs "
            "a full ordered sequence of steps, fills in missing ones, and optionally flags "
            "unnecessary steps or risks."
        ),
        "input_fields": [
            {
                "name": "goal_X",
                "description": "High-level goal the user wants to achieve.",
                "required": True
            },
            {
                "name": "known_steps_list",
                "description": (
                    "List of steps the user already believes are required, in any order."
                ),
                "required": True
            },
            {
                "name": "identify_unnecessary_steps_bool",
                "description": (
                    "If true, the model indicates which of the known steps may be unnecessary."
                ),
                "required": False
            }
        ],
        "output_fields": [
            {
                "name": "ordered_steps",
                "description": "Complete ordered list of steps needed to achieve the goal."
            },
            {
                "name": "step_annotations",
                "description": "Optional notes on dependencies, risks, or prerequisites."
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "goal_parsing",
                    "description": "Clarify and restate the goal X."
                },
                {
                    "name": "step_completion",
                    "description": (
                        "Generate missing steps and order both existing and new steps logically."
                    )
                },
                {
                    "name": "review_and_flagging",
                    "description": (
                        "Optionally mark unnecessary or high-risk steps and suggest improvements."
                    )
                }
            ]
        },
        "control_flags": {
            "max_step_count": "Upper bound on steps to keep plans manageable.",
            "group_into_phases": (
                "If true, cluster steps into phases such as 'Preparation', 'Execution', 'Follow-up'."
            )
        },
        "typical_use_cases": [
            "Planning a research project or experiment pipeline.",
            "Creating a study schedule or skill-learning roadmap.",
            "Outlining major milestones for a business or engineering project."
        ],
        "risks_and_misuses": [
            "Over-simplified plans that skip important real-world constraints.",
            "Overly detailed plans that become hard to follow.",
            "Plans that assume unrealistic resources or timelines."
        ],
        "example_prompt_skeleton": (
            "I want to achieve the following goal:\n"
            "{goal_X}\n\n"
            "I already know that I need to do these steps:\n"
            "{known_steps_list}\n\n"
            "Please create a complete, ordered sequence of steps that will help me reach the "
            "goal. Fill in any missing steps.\n"
            "{% if identify_unnecessary_steps_bool %}"
            "Also indicate if any of my listed steps are unnecessary or redundant.\n"
            "{% endif %}"
        )
    },
    {
        "pattern_name": "Semantic Filter",
        "pattern_family": "filtering_and_redaction",
        "primary_purpose": (
            "Filter or redact parts of text that match a semantic condition, such as a type of "
            "sensitive information or irrelevant content."
        ),
        "core_mechanism": (
            "Given some source text and a semantic filter condition X, the model returns a "
            "version of the text where all content satisfying X has been removed or transformed "
            "according to the specification."
        ),
        "input_fields": [
            {
                "name": "filter_condition_X",
                "description": (
                    "Semantic property that determines what should be removed, e.g. 'any PII', "
                    "'specific names', 'redundant content', or 'costs above a threshold'."
                ),
                "required": True
            },
            {
                "name": "retention_guidelines",
                "description": (
                    "Optional description of what must be preserved (e.g. structure, line count)."
                ),
                "required": False
            }
        ],
        "output_fields": [
            {
                "name": "filtered_text",
                "description": "The resulting text after removing elements that satisfy X."
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "condition_interpretation",
                    "description": "Model interprets the filter condition in the context of the text."
                },
                {
                    "name": "filter_application",
                    "description": "Model removes or transforms segments that match the condition."
                },
                {
                    "name": "structural_cleanup",
                    "description": (
                        "Model cleans up the remaining text to ensure readability and coherence."
                    )
                }
            ]
        },
        "control_flags": {
            "strictness_level": (
                "How aggressively to filter content (low, medium, high)."
            ),
            "preserve_formatting": (
                "If true, preserve layout markers such as headings and bullet points."
            )
        },
        "typical_use_cases": [
            "Redacting PII before storing user data.",
            "Removing redundant or boilerplate text from emails or logs.",
            "Filtering out off-topic content from research notes."
        ],
        "risks_and_misuses": [
            "Over-filtering important information by misinterpreting the condition.",
            "Under-filtering sensitive data in ambiguous cases.",
            "Changing the meaning of the text when too much is removed."
        ],
        "example_prompt_skeleton": (
            "Here is some text. Remove all content that matches the following condition:\n"
            "{filter_condition_X}\n\n"
            "Return only the filtered version of the text.\n"
            "{% if retention_guidelines %}"
            "Make sure to follow these constraints on what should remain:\n"
            "{retention_guidelines}\n"
            "{% endif %}"
        )
    },
    {
        "pattern_name": "Tail Generation",
        "pattern_family": "interaction_flow",
        "primary_purpose": (
            "Standardize how responses end, such as always adding a disclaimer or a follow-up "
            "question, to guide the next interaction."
        ),
        "core_mechanism": (
            "The model is instructed that every response must end with a specific tail segment, "
            "such as repeating key options, adding a disclaimer, or asking the user a question "
            "about next steps."
        ),
        "input_fields": [
            {
                "name": "tail_Y_or_followup_X",
                "description": (
                    "Description of the required tail content (e.g. disclaimer text, list of "
                    "options, or a question asking what to do next)."
                ),
                "required": True
            }
        ],
        "output_fields": [
            {
                "name": "main_content",
                "description": "Primary response to the user’s request."
            },
            {
                "name": "tail_segment",
                "description": "Final standardized segment appended to the response."
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "core_response",
                    "description": "Model generates the main content normally."
                },
                {
                    "name": "tail_attachment",
                    "description": (
                        "Model appends the required tail content verbatim or according to a pattern."
                    )
                }
            ]
        },
        "control_flags": {
            "tail_separator": "String used to separate main content from tail (e.g. '\\n\\n---\\n').",
            "enforce_consistency": (
                "If true, the tail wording must remain identical across responses."
            )
        },
        "typical_use_cases": [
            "Agents that always end with a follow-up question to maintain conversation.",
            "Safety or legal disclaimers appended to certain types of content.",
            "Stepwise workflows that always ask what to do next."
        ],
        "risks_and_misuses": [
            "Users may ignore repeated disclaimers, reducing perceived impact.",
            "The tail may become misleading if context changes but the template does not.",
            "For long tails, verbosity can annoy users."
        ],
        "example_prompt_skeleton": (
            "Whenever you respond to me, first generate the main answer.\n"
            "Then, at the very end of your response, append the following tail:\n"
            "{tail_Y_or_followup_X}"
        )
    },
    {
        "pattern_name": "Template Pattern",
        "pattern_family": "format_control",
        "primary_purpose": (
            "Force the model’s output to follow a user-specified template with placeholders."
        ),
        "core_mechanism": (
            "The user supplies a template and defines placeholder syntax. The model fills "
            "the placeholders with appropriate content while preserving the rest of the "
            "template’s structure and formatting."
        ),
        "input_fields": [
            {
                "name": "placeholder_syntax_X",
                "description": (
                    "Description of how placeholders are represented (e.g. CAPITALIZED WORDS, "
                    "'<placeholder>', '{FIELD_NAME}')."
                ),
                "required": True
            },
            {
                "name": "template_pattern",
                "description": "The actual template text that should be preserved.",
                "required": True
            }
        ],
        "output_fields": [
            {
                "name": "filled_template",
                "description": "The template with placeholders replaced by appropriate content."
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "template_parsing",
                    "description": "Model identifies all placeholders within the template."
                },
                {
                    "name": "content_generation_for_placeholders",
                    "description": (
                        "Model generates content for each placeholder based on instructions "
                        "and user context."
                    )
                },
                {
                    "name": "template_reassembly",
                    "description": "Model reassembles the full template with filled placeholders."
                }
            ]
        },
        "control_flags": {
            "allow_partial_fill": (
                "If true, the model can leave some placeholders untouched (e.g. for later editing)."
            ),
            "preserve_whitespace": (
                "If true, whitespace and layout must be preserved exactly."
            )
        },
        "typical_use_cases": [
            "Generating structured reports or letters.",
            "Producing LaTeX, Markdown, or HTML skeletons filled with research content.",
            "Creating consistent document formats across a dataset."
        ],
        "risks_and_misuses": [
            "Model may alter or drop parts of the template if not explicitly constrained.",
            "Incorrectly inferred meaning of ambiguous placeholders.",
            "Overfitting content to a template that does not quite fit the task."
        ],
        "example_prompt_skeleton": (
            "I will give you a template. {placeholder_syntax_X} are placeholders that you must fill.\n\n"
            "Template:\n{template_pattern}\n\n"
            "Fill in each placeholder with appropriate content based on my instructions. "
            "Preserve all other text and formatting exactly."
        )
    },
    {
        "pattern_name": "Chain-of-Thought",
        "pattern_family": "reasoning",
        "primary_purpose": (
            "Improve reasoning quality by making the model explicitly walk through "
            "intermediate steps before giving a final answer."
        ),
        "core_mechanism": (
            "The prompt instructs the model to break down a task into logical steps, reason "
            "through them, and only then present a final answer. Reasoning can be formatted "
            "as numbered steps, bullet lists, or short paragraphs."
        ),
        "input_fields": [
            {
                "name": "task_description",
                "description": "Problem or question that requires multi-step reasoning.",
                "required": True
            },
            {
                "name": "reasoning_style",
                "description": (
                    "Preferred style for intermediate steps (e.g. 'numbered steps', "
                    "'brief bullet points', 'detailed algebraic derivation')."
                ),
                "required": False
            },
            {
                "name": "max_steps_hint",
                "description": (
                    "Optional guidance on how many steps to use before concluding."
                ),
                "required": False
            }
        ],
        "output_fields": [
            {
                "name": "reasoning_steps",
                "description": "Sequence of intermediate steps or thoughts leading to a conclusion."
            },
            {
                "name": "final_answer",
                "description": "The final statement or result after the reasoning steps."
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "problem_restating",
                    "description": "Model restates the task to ensure understanding."
                },
                {
                    "name": "stepwise_reasoning",
                    "description": "Model decomposes the problem into steps and solves each step."
                },
                {
                    "name": "answer_extraction",
                    "description": "Model summarizes the result as a concise final answer."
                }
            ]
        },
        "control_flags": {
            "hide_reasoning_from_user": (
                "Whether to show reasoning steps to the user or keep them internal."
            ),
            "max_reasoning_length": "Limit on the total length of the reasoning trace."
        },
        "typical_use_cases": [
            "Mathematical proofs and derivations.",
            "Complex research questions that involve multiple constraints.",
            "Logical puzzles and planning problems."
        ],
        "risks_and_misuses": [
            "Model can produce plausible but incorrect reasoning chains.",
            "Exposing full chains to users can make errors look more convincing.",
            "Long reasoning traces can be slow and costly."
        ],
        "example_prompt_skeleton": (
            "You are an expert assistant.\n"
            "For the following task, think through the problem step by step before giving your "
            "final answer.\n\n"
            "Task: {task_description}\n\n"
            "{% if reasoning_style %}"
            "Use this style for your reasoning: {reasoning_style}\n"
            "{% endif %}\n"
            "First list your reasoning steps. Then, on a new line, write 'Final answer:' "
            "followed by your conclusion."
        )
    }
]


react_patterns = [
    {
        "pattern_name": "ReAct – Knowledge QA (Dense Reason + Act)",
        "pattern_family": "Reason+Action / Tool-Augmented QA",
        "primary_purpose": (
            "Answer knowledge-intensive questions by interleaving chain-of-thought reasoning "
            "with explicit tool calls (Search, Lookup, Finish) against an external knowledge "
            "source such as Wikipedia."
        ),
        "core_mechanism": (
            "The model alternates between free-form reasoning steps (Thought) and symbolic "
            "actions (Action) that query an external environment. Each Action produces an "
            "Observation, which is appended to the context and used in subsequent Thoughts. "
            "The trajectory follows the pattern:\n\n"
            "Question → [Thought → Action → Observation]×k → Finish[answer].\n\n"
            "Thoughts decompose the problem, choose what to retrieve next, interpret "
            "observations, and synthesize the final answer, while Actions handle concrete "
            "retrieval via a restricted API (e.g. Search[entity], Lookup[string], Finish[answer])."
        ),
        "input_fields": [
            {
                "name": "task_instruction",
                "description": (
                    "High-level natural-language description of the task, e.g. "
                    "\"You are an agent that answers questions by reasoning and by "
                    "calling a Wikipedia API with Search[], Lookup[], Finish[].\""
                ),
                "required": True
            },
            {
                "name": "action_space_spec",
                "description": (
                    "Formal description of allowed actions and their syntax, e.g. "
                    "Search[entity], Lookup[string], Finish[answer], plus what each returns."
                ),
                "required": True
            },
            {
                "name": "format_spec",
                "description": (
                    "Textual format contract for the trajectory, typically: "
                    "Question, Thought k, Action k, Observation k, followed by a final Finish[]."
                ),
                "required": True
            },
            {
                "name": "few_shot_trajectories",
                "description": (
                    "1–6 fully written ReAct trajectories that show alternation of "
                    "Thought / Action / Observation until Finish[answer]. Each example "
                    "uses real calls to the environment and correct final answers."
                ),
                "required": True
            },
            {
                "name": "query_or_claim",
                "description": (
                    "The user’s question or fact-checking claim to solve in the new instance."
                ),
                "required": True
            },
            {
                "name": "step_budget",
                "description": (
                    "Maximum number of Thought/Action steps before the model must call Finish[]. "
                    "Used to prevent infinite loops."
                ),
                "required": False
            },
            {
                "name": "style_or_safety_instructions",
                "description": (
                    "Optional guardrails on style (e.g. concise final answer only) and on tool "
                    "usage (e.g. stay within domain, don’t call disallowed URLs)."
                ),
                "required": False
            }
        ],
        "output_fields": [
            {
                "name": "reasoning_trace",
                "description": (
                    "Full interleaved sequence of Thought, Action, and Observation steps used to "
                    "arrive at the answer."
                )
            },
            {
                "name": "tool_calls",
                "description": (
                    "Structured representation of each Action (name, arguments, step index), "
                    "usable for logging or execution."
                )
            },
            {
                "name": "tool_observations",
                "description": (
                    "Text returned by each tool call, appended to context as Observation k."
                )
            },
            {
                "name": "final_answer",
                "description": (
                    "The argument of the last Finish[answer] action, or the answer extracted "
                    "from it; this is what is shown to the end-user."
                )
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "setup",
                    "description": (
                        "Explain the task, define the action space, and show 1–6 complete "
                        "ReAct example trajectories (Question → Thought/Action/Observation → Finish)."
                    )
                },
                {
                    "name": "initial_reasoning",
                    "description": (
                        "For a new Question/Claim, generate Thought 1 that decomposes the task "
                        "and decides the first Action (usually a Search[...])."
                    )
                },
                {
                    "name": "reason_act_loop",
                    "description": (
                        "Alternate between Thought k and Action k. After each tool call, inject "
                        "Observation k (the tool result) into the context. Thoughts use both "
                        "internal knowledge and observations to decide the next tool call or "
                        "to conclude with Finish[answer]."
                    )
                },
                {
                    "name": "termination",
                    "description": (
                        "When sufficient evidence is gathered or the step budget is reached, "
                        "issue Finish[answer]. Extract the answer and optionally strip the "
                        "ReAct trace for user-facing display."
                    )
                },
                {
                    "name": "optional_backoff",
                    "description": (
                        "If the model fails to reach Finish[answer] in the allotted steps, "
                        "or appears uncertain, fall back to a pure CoT (self-consistency) "
                        "prompt or vice versa (CoT → ReAct) as described in the paper."
                    )
                }
            ]
        },
        "control_flags": {
            "max_steps": "Integer limit on Thought/Action pairs (e.g. 5–7).",
            "allowed_actions": [
                "Search[...]", "Lookup[...]", "Finish[...]"
            ],
            "must_follow_format": True,
            "allow_free_text_between_actions": False,
            "stop_on_finish": True,
            "external_env_guardrails": (
                "Environment is restricted (e.g. only Wikipedia API) and sandboxed to avoid "
                "unsafe browsing or side-effects."
            )
        },
        "typical_use_cases": [
            "Multi-hop question answering using external corpora (e.g. Wikipedia).",
            "Fact verification tasks (SUPPORTS / REFUTES / NOT ENOUGH INFO).",
            "Any task where internal model knowledge is insufficient or may be outdated."
        ],
        "risks_and_misuses": [
            "Reasoning loops where the model repeats the same Search/Lookup steps.",
            "Over-reliance on weak retrieval APIs leading to errors when search results are poor.",
            "Long trajectories that increase latency and cost.",
            "Possible misuse if the external environment is not sandboxed (privacy / safety issues)."
        ],
        "example_prompt_skeleton": (
            "You are an intelligent agent that can **think** and **act** to answer questions.\n"
            "You have access to a Wikipedia API with the following actions:\n"
            "  • Search[entity]: returns the first 5 sentences of the page for `entity`, or\n"
            "    suggested similar entities if it does not exist.\n"
            "  • Lookup[string]: returns the next sentence in the current page that contains `string`.\n"
            "  • Finish[answer]: stop and return `answer`.\n\n"
            "For each problem, use the following format:\n"
            "Question: <user question>\n"
            "Thought 1: <explain what you will do first>\n"
            "Action 1: Search[...]\n"
            "Observation 1: <result from the search API>\n"
            "Thought 2: <update plan based on Observation 1>\n"
            "Action 2: Lookup[...] or Search[...]\n"
            "Observation 2: <result>\n"
            "... (repeat Thought/Action/Observation as needed) ...\n"
            "Thought k: <I now know the answer because ...>\n"
            "Action k: Finish[final answer]\n\n"
            "Here are some examples:\n"
            "<insert 3–6 fully written ReAct trajectories from the paper or your own data>\n\n"
            "Now answer this new question using the same format.\n"
            "Question: {question}\n"
            "Thought 1:"
        ),
        "notes": (
            "This is the canonical ReAct pattern for knowledge-intensive tasks: Thoughts are "
            "dense (appearing before almost every Action), and the action space is small and "
            "tool-like. It explicitly separates internal reasoning from external retrieval, which "
            "improves factuality and interpretability over pure CoT, while avoiding the blind "
            "exploration of act-only agents."
        )
    },
    {
        "pattern_name": "ReAct – Decision Environment (Sparse Reason + Act)",
        "pattern_family": "Reason+Action / Interactive Decision-Making",
        "primary_purpose": (
            "Control agents in interactive environments (games, web UIs, robots) by allowing the "
            "model to interleave high-level natural-language reasoning with low-level domain actions."
        ),
        "core_mechanism": (
            "Use a large language model as a policy over an **augmented action space** that "
            "includes both environment actions (go, open, take, click, buy, clean, etc.) and "
            "language thoughts (think: ...). Observations from the environment are converted to "
            "text and appended to the context. Thoughts are **sparse**: the model chooses when "
            "to insert them to decompose goals, track progress, decide next subgoals, or reflect "
            "on what to do next."
        ),
        "input_fields": [
            {
                "name": "task_instruction",
                "description": (
                    "Natural-language description of the high-level goal in the environment, e.g. "
                    "\"Your task is to put a clean lettuce on the dining table.\""
                ),
                "required": True
            },
            {
                "name": "environment_description",
                "description": (
                    "A brief description of the world, objects, and what actions are possible, "
                    "e.g. textual room description, list of visible objects, or a web UI schema."
                ),
                "required": True
            },
            {
                "name": "action_space_spec",
                "description": (
                    "Catalog of environment actions and their syntax, e.g. "
                    "go to OBJ, open OBJ, take OBJ from SRC, clean OBJ with TOOL, "
                    "search QUERY, click ID, buy, etc."
                ),
                "required": True
            },
            {
                "name": "format_spec",
                "description": (
                    "Turn-taking format: each line begins with either an environment event "
                    "or an agent event, e.g.\n"
                    "  > think: ...\n"
                    "  > go to fridge 1\n"
                    "  Observation: The fridge 1 is closed.\n"
                    "  > open fridge 1\n"
                    "  Observation: ...\n"
                    "until the goal is satisfied."
                ),
                "required": True
            },
            {
                "name": "few_shot_trajectories",
                "description": (
                    "1–3 demonstrations per task type showing how the agent decomposes goals "
                    "with occasional think: lines and uses environment actions to complete tasks."
                ),
                "required": True
            },
            {
                "name": "max_action_budget",
                "description": (
                    "Optional limit on the total number of environment actions to avoid unbounded "
                    "exploration."
                ),
                "required": False
            }
        ],
        "output_fields": [
            {
                "name": "action_trajectory",
                "description": (
                    "Sequence of issued actions (with arguments) from start to success or failure."
                )
            },
            {
                "name": "reasoning_trace",
                "description": (
                    "Sparse think: lines that show goal decomposition, progress tracking, and "
                    "commonsense reasoning about the environment."
                )
            },
            {
                "name": "final_env_state",
                "description": (
                    "Textual description of the environment when the agent finishes (success/fail)."
                )
            }
        ],
        "workflow_structure": {
            "phases": [
                {
                    "name": "initial_goal_decomposition",
                    "description": (
                        "Emit a think: line that breaks the high-level goal into subgoals "
                        "(e.g. find lettuce → clean lettuce → place lettuce on table)."
                    )
                },
                {
                    "name": "exploration_and_subgoal_execution",
                    "description": (
                        "Use environment actions (go/open/take/clean/etc.) to achieve the current "
                        "subgoal. Insert think: lines when helpful to choose likely locations, "
                        "update which subgoal is active, or re-plan."
                    )
                },
                {
                    "name": "progress_tracking",
                    "description": (
                        "Periodically summarize in think: what has been accomplished and what remains "
                        "e.g. \"Now I have taken the lettuce. Next, I need to go to the sink.\""
                    )
                },
                {
                    "name": "termination",
                    "description": (
                        "Stop when the environment signals success (goal satisfied) or when "
                        "the action budget is consumed. Optionally emit a final think: summary."
                    )
                }
            ]
        },
        "control_flags": {
            "max_actions": "Hard limit on action count (distinct from think: lines).",
            "allow_think_lines": True,
            "think_prefix": "think:",
            "must_obey_action_grammar": True,
            "stop_on_success_signal": True
        },
        "typical_use_cases": [
            "Text-based games and embodied household tasks (e.g. ALFWorld).",
            "Web navigation / shopping environments (e.g. WebShop).",
            "Any environment where actions are discrete and observations can be textualized."
        ],
        "risks_and_misuses": [
            "Getting stuck in local loops (e.g. repeatedly trying an impossible action).",
            "Incorrect commonsense assumptions about where objects are or what actions do.",
            "Costs from long trajectories in large environments.",
            "If connected to real systems (e.g. real shopping carts or robots), unsafe or "
            "undesired actions without additional safety layers."
        ],
        "example_prompt_skeleton": (
            "You are an agent acting in a text environment. You can **think** in natural "
            "language and **act** using environment commands.\n\n"
            "Format:\n"
            "Environment: <initial room / web page description>\n"
            "Your task is to: {task_instruction}\n"
            "> think: <describe your subgoal or plan>\n"
            "> <action 1>\n"
            "Observation: <result of action 1>\n"
            "> think: <update plan if needed>\n"
            "> <action 2>\n"
            "Observation: <result of action 2>\n"
            "... (continue) ...\n"
            "(Stop when the task is complete.)\n\n"
            "Here are some examples:\n"
            "<insert 1–3 trajectories per task type, showing sparse think: lines>\n\n"
            "Now solve this new task using the same format.\n"
            "Environment: {env_description}\n"
            "Your task is to: {task_instruction}"
        ),
        "notes": (
            "Compared to the QA variant, Thoughts here are sparse—often only at key decision "
            "points—because trajectories can be long (tens of actions). The pattern is well "
            "suited for few-shot prompting in structured environments and can outperform pure "
            "imitation / RL baselines when demonstrations are limited."
        )
    }
]
