import type { AlertCategory } from '@/types/coherence';

/**
 * Color palette for alert categories
 */
export const CATEGORY_COLORS: Record<AlertCategory, string> = {
  Legal: '#3B82F6', // Blue
  Financial: '#10B981', // Green
  Technical: '#8B5CF6', // Purple
  Schedule: '#F59E0B', // Orange
  Scope: '#06B6D4', // Cyan
  Quality: '#6366F1', // Indigo
} as const;

/**
 * Background colors for category cards (lighter versions)
 */
export const CATEGORY_BG_COLORS: Record<AlertCategory, string> = {
  Legal: '#EFF6FF', // Blue-50
  Financial: '#ECFDF5', // Green-50
  Technical: '#F5F3FF', // Purple-50
  Schedule: '#FFFBEB', // Orange-50
  Scope: '#ECFEFF', // Cyan-50
  Quality: '#EEF2FF', // Indigo-50
} as const;

/**
 * Border colors for category cards
 */
export const CATEGORY_BORDER_COLORS: Record<AlertCategory, string> = {
  Legal: '#DBEAFE', // Blue-100
  Financial: '#D1FAE5', // Green-100
  Technical: '#EDE9FE', // Purple-100
  Schedule: '#FEF3C7', // Orange-100
  Scope: '#CFFAFE', // Cyan-100
  Quality: '#E0E7FF', // Indigo-100
} as const;

/**
 * Text colors for category labels
 */
export const CATEGORY_TEXT_COLORS: Record<AlertCategory, string> = {
  Legal: '#1E40AF', // Blue-800
  Financial: '#047857', // Green-700
  Technical: '#6D28D9', // Purple-700
  Schedule: '#B45309', // Orange-700
  Scope: '#0E7490', // Cyan-700
  Quality: '#4338CA', // Indigo-700
} as const;

/**
 * Icon names for each category (using lucide-react icons)
 */
export const CATEGORY_ICONS: Record<AlertCategory, string> = {
  Legal: 'Scale',
  Financial: 'DollarSign',
  Technical: 'Wrench',
  Schedule: 'Calendar',
  Scope: 'Target',
  Quality: 'ShieldCheck',
} as const;
