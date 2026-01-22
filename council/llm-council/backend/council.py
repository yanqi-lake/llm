"""3-stage LLM Council orchestration."""

from typing import List, Dict, Any, Tuple
from .openrouter import query_models_parallel, query_model
from .config import CODE_EDITOR_MODELS, CODE_ANALYZER_MODEL, CHAIRMAN_MODEL


async def stage1_collect_responses(user_query: str) -> List[Dict[str, Any]]:
    """
    Stage 1: Code Editor models solve the problem independently.

    Args:
        user_query: The user's question

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    messages = [{"role": "user", "content": user_query}]

    # Query code editor models in parallel
    responses = await query_models_parallel(CODE_EDITOR_MODELS, messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, Any]]:
    """
    Stage 2: Code Editor models rank responses, then Code Analyzer analyzes top-ranked code.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping, analyzer_result)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are a Code Editor evaluating different code solutions to the following programming problem:

Problem: {user_query}

Here are the code solutions from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each code solution individually. For each solution, explain what it does well and what it does poorly in terms of:
   - Code correctness and functionality
   - Code quality and readability
   - Best practices and efficiency
   - Error handling and robustness
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from code editor models in parallel
    responses = await query_models_parallel(CODE_EDITOR_MODELS, messages)

    # Format ranking results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    # Calculate aggregate rankings to find the top-ranked solution
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
    if aggregate_rankings:
        top_solution_label = aggregate_rankings[0]["model"]  # Best ranked model
        top_solution = next((result for result in stage1_results if result["model"] == top_solution_label), None)

        if top_solution:
            # Code Analyzer analyzes the top-ranked solution
            analyzer_prompt = f"""You are a Code Analyzer. Your task is to perform a detailed analysis of the following code solution and provide specific improvement suggestions.

Original Problem: {user_query}

Top-ranked Code Solution (from {top_solution['model']}):
{top_solution['response']}

Please provide:
1. A detailed analysis of the code's strengths and weaknesses
2. Specific suggestions for improvements, including:
   - Code optimization opportunities
   - Better error handling
   - Improved readability and maintainability
   - Additional features or edge cases to consider
   - Security considerations if applicable
3. If possible, suggest concrete code modifications

Be thorough but practical in your analysis."""

            analyzer_messages = [{"role": "user", "content": analyzer_prompt}]
            analyzer_response = await query_model(CODE_ANALYZER_MODEL, analyzer_messages)

            analyzer_result = {
                "model": CODE_ANALYZER_MODEL,
                "analysis": analyzer_response.get('content', '') if analyzer_response else "Analysis failed",
                "target_solution": top_solution_label
            }
        else:
            analyzer_result = {
                "model": CODE_ANALYZER_MODEL,
                "analysis": "Could not find top-ranked solution for analysis",
                "target_solution": None
            }
    else:
        analyzer_result = {
            "model": CODE_ANALYZER_MODEL,
            "analysis": "No rankings available for analysis",
            "target_solution": None
        }

    return stage2_results, label_to_model, analyzer_result


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    analyzer_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response based on analyzer suggestions.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        analyzer_result: Analysis from Code Analyzer

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    analyzer_text = f"Code Analyzer ({analyzer_result['model']}):\n{analyzer_result['analysis']}"

    chairman_prompt = f"""You are the Chairman of a Code Review Council. Multiple AI Code Editor models have provided solutions to a programming problem, ranked each other's solutions, and a Code Analyzer has reviewed the top-ranked solution.

Your role is to synthesize all this information into a final, improved code solution.

Original Problem: {user_query}

STAGE 1 - Code Editor Solutions:
{stage1_text}

STAGE 2 - Peer Rankings by Code Editors:
{stage2_text}

STAGE 3 - Code Analyzer Review of Top Solution:
{analyzer_text}

Your task as Chairman is to:
1. Review all the individual solutions and their rankings
2. Consider the Code Analyzer's suggestions for improvement
3. Create a final, improved code solution that incorporates the best elements from all solutions
4. Address any issues identified by the Code Analyzer
5. Ensure the final solution is correct, efficient, readable, and robust

Provide a comprehensive final solution that represents the council's collective wisdom, with:
- The complete, improved code
- Explanations of key improvements made
- Any additional considerations or best practices

Final Solution:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(user_query: str) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(user_query)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect rankings and analyzer feedback
    stage2_results, label_to_model, analyzer_result = await stage2_collect_rankings(user_query, stage1_results)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        analyzer_result
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "analyzer_result": analyzer_result
    }

    return stage1_results, stage2_results, stage3_result, metadata
