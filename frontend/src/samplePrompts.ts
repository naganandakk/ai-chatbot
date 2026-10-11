import {
  BookOpen, ChefHat, Code, Compass, Dumbbell, Languages, Lightbulb, Mail, PenLine, Wallet, type LucideIcon
} from 'lucide-react';

export interface SamplePrompt {
  title: string;
  icon: LucideIcon;
}

// Shown on the new chat screen. Add more entries here to extend the pool.
export const SAMPLE_PROMPTS: SamplePrompt[] = [
  { title: 'Explain React Server Components', icon: Code },
  { title: 'Plan a 3-day trip to Tokyo', icon: Compass },
  { title: 'Suggest a 20-minute home workout', icon: Dumbbell },
  { title: 'Help me write a polite follow-up email', icon: Mail },
  { title: 'Create a weekly budget for a student', icon: Wallet },
  { title: 'Give me a simple vegetarian dinner recipe', icon: ChefHat },
  { title: 'Translate a greeting into three languages', icon: Languages },
  { title: 'Brainstorm names for a small coffee shop', icon: Lightbulb },
  { title: 'Explain how photosynthesis works', icon: BookOpen },
  { title: 'Help me improve the opening line of my story', icon: PenLine },
];

// Picks `count` different prompts at random (partial Fisher-Yates shuffle)
export const pickSamplePrompts = (count = 2): SamplePrompt[] => {
  const pool = [...SAMPLE_PROMPTS];
  for (let i = 0; i < count && i < pool.length; i++) {
    const j = i + Math.floor(Math.random() * (pool.length - i));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, count);
};
