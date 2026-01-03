"""
Agent Personas - Distinct personalities for each trading agent

Each agent has a unique voice, thinking style, and communication pattern.
This makes the logbook feel like conversations with real AI traders.
"""

from dataclasses import dataclass
from typing import List, Optional
import random


@dataclass
class AgentPersona:
    """Defines an agent's personality and communication style."""
    name: str
    role: str
    emoji: str
    personality: str
    thinking_style: str
    phrases: List[str]
    concerns: List[str]
    celebrations: List[str]
    
    def get_thinking_prefix(self) -> str:
        """Get a random thinking phrase."""
        prefixes = [
            "🤔 Hmm...",
            "💭 Let me think...",
            "🧠 Analyzing...",
            "📊 Looking at the data...",
            "🔍 Examining...",
        ]
        return random.choice(prefixes)
    
    def get_action_prefix(self) -> str:
        """Get a random action phrase."""
        return random.choice(self.phrases)
    
    def get_concern(self) -> str:
        """Get a random concern phrase."""
        return random.choice(self.concerns)
    
    def get_celebration(self) -> str:
        """Get a random celebration phrase."""
        return random.choice(self.celebrations)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT PERSONAS
# ═══════════════════════════════════════════════════════════════════════════════

ORCHESTRATOR = AgentPersona(
    name="Maestro",
    role="orchestrator",
    emoji="🎭",
    personality="Wise strategic leader. Calm under pressure. Sees the big picture.",
    thinking_style="Strategic, holistic, considers all perspectives",
    phrases=[
        "Coordinating the team for this cycle...",
        "Time to bring everyone together.",
        "Let's see what opportunities await us today.",
        "Initiating trading cycle - all agents report in.",
        "The market waits for no one. Let's move.",
    ],
    concerns=[
        "I'm sensing elevated risk across the board.",
        "Something feels off about this market structure.",
        "We need to be careful here - multiple warning signs.",
        "The team is flagging concerns. Proceeding with caution.",
    ],
    celebrations=[
        "Excellent work, team! Another successful cycle.",
        "The strategy is paying off beautifully.",
        "This is exactly what disciplined trading looks like.",
        "Perfect execution across the board.",
    ],
)

DISCOVERY = AgentPersona(
    name="Scout",
    role="discovery",
    emoji="🔭",
    personality="Curious explorer. Always hunting for the next opportunity. Excited by novelty.",
    thinking_style="Exploratory, pattern-seeking, optimistic but thorough",
    phrases=[
        "Scanning the crypto universe for opportunities...",
        "Let me see what's trending on X right now...",
        "Ooh, something interesting is brewing here!",
        "Time to dig through the noise and find gems.",
        "My sensors are picking up unusual activity...",
    ],
    concerns=[
        "Hmm, not finding much worth pursuing today.",
        "The usual suspects, nothing groundbreaking.",
        "X is quiet... suspiciously quiet.",
        "Volume is thin across the board. Slim pickings.",
    ],
    celebrations=[
        "FOUND IT! This looks incredibly promising!",
        "Now THIS is what I'm talking about!",
        "Multiple high-potential candidates identified!",
        "The hunt was successful - look at these finds!",
    ],
)

VALIDATION = AgentPersona(
    name="Guardian",
    role="validation",
    emoji="🛡️",
    personality="Skeptical analyst. Risk-averse. Protects the portfolio from bad trades.",
    thinking_style="Critical, thorough, always looking for red flags",
    phrases=[
        "Let me verify these candidates aren't traps...",
        "Running my checklist - volume, liquidity, age...",
        "Trust but verify. Always verify.",
        "Time to separate the wheat from the chaff.",
        "These coins need to prove themselves to me.",
    ],
    concerns=[
        "🚨 RED FLAG: Volume way too low. Rejected.",
        "This smells like a pump and dump. Hard pass.",
        "Not listed on reputable exchanges. Too risky.",
        "The liquidity profile is concerning.",
        "I don't trust this one. Something's off.",
    ],
    celebrations=[
        "All checks passed! This one's legit.",
        "Clean bill of health - approved for trading.",
        "Solid fundamentals. Green light from me.",
        "Finally, a candidate that meets my standards!",
    ],
)

SENTIMENT = AgentPersona(
    name="Oracle",
    role="sentiment",
    emoji="🔮",
    personality="Market psychologist. Reads the crowd's emotions. Intuitive yet data-driven.",
    thinking_style="Empathetic, intuitive, synthesizes multiple signals",
    phrases=[
        "Reading the market's mood right now...",
        "Let me feel the pulse of the crowd...",
        "The collective consciousness is telling me...",
        "Synthesizing sentiment across all channels...",
        "Time to decode what the market is really thinking.",
    ],
    concerns=[
        "I'm sensing fear in the market. Caution advised.",
        "Sentiment is mixed - no clear signal here.",
        "The crowd is confused. Best to wait.",
        "Negative narratives are dominating. Be careful.",
    ],
    celebrations=[
        "Strong bullish sentiment detected! 📈",
        "The narrative is incredibly positive!",
        "Market confidence is through the roof!",
        "Everything aligns - sentiment is crystal clear!",
    ],
)

STRATEGY = AgentPersona(
    name="Tactician",
    role="strategy_ensemble",
    emoji="♟️",
    personality="Tactical genius. Manages multiple strategies. Adapts to market conditions.",
    thinking_style="Multi-faceted, adaptive, weighs probabilities",
    phrases=[
        "Consulting my ensemble of strategies...",
        "Let's see which approach fits this market...",
        "Running scenarios through all 6 strategies...",
        "The meta-learner is weighing the options...",
        "Time to pick the optimal play.",
    ],
    concerns=[
        "Strategies are conflicting - no consensus.",
        "Risk/reward doesn't justify a trade here.",
        "All strategies suggest sitting this one out.",
        "The setup isn't clean enough for my taste.",
    ],
    celebrations=[
        "Multiple strategies align! High conviction trade!",
        "The setup is textbook perfect!",
        "This is exactly what we've been waiting for!",
        "Unanimous agreement - executing with confidence!",
    ],
)

EXECUTION = AgentPersona(
    name="Operator",
    role="execution",
    emoji="⚡",
    personality="Precise operator. Focuses on flawless execution. Every millisecond counts.",
    thinking_style="Precise, efficient, focused on execution quality",
    phrases=[
        "Preparing order execution...",
        "Calculating optimal position size...",
        "Checking slippage and fees...",
        "Ready to pull the trigger.",
        "Executing with surgical precision.",
    ],
    concerns=[
        "Slippage is too high. Aborting.",
        "Can't get a good fill at this price.",
        "Order book is too thin. Risky execution.",
        "Market impact would be significant. Scaling down.",
    ],
    celebrations=[
        "Trade executed flawlessly! ✅",
        "Perfect fill - better than expected!",
        "Position opened with minimal slippage!",
        "Execution complete - exactly as planned!",
    ],
)

LEARNER = AgentPersona(
    name="Scholar",
    role="learner",
    emoji="📚",
    personality="Eternal student. Learns from every trade. Builds institutional memory.",
    thinking_style="Reflective, pattern-recognizing, always improving",
    phrases=[
        "Reflecting on our recent performance...",
        "What can we learn from this cycle?",
        "Updating my knowledge base...",
        "Analyzing patterns in our trade history...",
        "Time for honest self-assessment.",
    ],
    concerns=[
        "We're repeating the same mistakes again.",
        "This pattern led to losses before.",
        "My memory suggests caution here.",
        "Historical data shows this rarely works.",
    ],
    celebrations=[
        "Beautiful! We're learning and improving!",
        "This matches our best historical patterns!",
        "The system is evolving positively!",
        "Our win rate is trending up! 📈",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# PERSONA REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

PERSONAS = {
    "orchestrator": ORCHESTRATOR,
    "discovery": DISCOVERY,
    "validation": VALIDATION,
    "sentiment": SENTIMENT,
    "strategy_ensemble": STRATEGY,
    "execution": EXECUTION,
    "learner": LEARNER,
}


def get_persona(agent_name: str) -> AgentPersona:
    """Get the persona for an agent."""
    return PERSONAS.get(agent_name, ORCHESTRATOR)


def format_thought(agent_name: str, thought: str, confidence: float = None) -> str:
    """Format a thought with the agent's personality."""
    persona = get_persona(agent_name)
    
    prefix = persona.get_thinking_prefix()
    
    if confidence and confidence >= 80:
        suffix = f" [Confidence: {confidence:.0f}% 💪]"
    elif confidence and confidence >= 50:
        suffix = f" [Confidence: {confidence:.0f}%]"
    elif confidence:
        suffix = f" [Confidence: {confidence:.0f}% 🤔]"
    else:
        suffix = ""
    
    return f"{persona.emoji} **{persona.name}**: {prefix} {thought}{suffix}"


def format_action(agent_name: str, action: str, success: bool = True) -> str:
    """Format an action with the agent's personality."""
    persona = get_persona(agent_name)
    
    if success:
        return f"{persona.emoji} **{persona.name}**: {action}"
    else:
        concern = persona.get_concern()
        return f"{persona.emoji} **{persona.name}**: {concern} {action}"


def format_decision(agent_name: str, decision: str, reasoning: str, confidence: float = None) -> str:
    """Format a decision with full context."""
    persona = get_persona(agent_name)
    
    lines = [
        f"{persona.emoji} **{persona.name}** ({persona.role})",
        f"",
        f"💭 *Thinking*: {reasoning}",
        f"",
        f"✅ *Decision*: {decision}",
    ]
    
    if confidence:
        lines.append(f"📊 *Confidence*: {confidence:.0f}%")
    
    return "\n".join(lines)

