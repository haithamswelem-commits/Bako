import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import {
  PulseConfirmDialog,
  PulseButton,
  PulseCard,
  PulseErrorState,
  PulseFinancialValue,
} from './PulsePrimitives'

describe('Pulse primitives', () => {
  it('renders the amount and currency as separate readable elements', () => {
    render(<PulseFinancialValue amount="12,345.67" />)

    expect(screen.getByText('12,345.67')).toHaveClass('pulse-financial-amount')
    expect(screen.getByText('EGP')).toHaveClass('pulse-financial-currency')
  })

  it('returns the selected confirmation result', () => {
    const onResolve = vi.fn()
    render(
      <PulseConfirmDialog
        request={{ title: 'Delete?', message: 'This cannot be undone.' }}
        onResolve={onResolve}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onResolve).toHaveBeenCalledWith(true)
  })

  it('announces shared error states', () => {
    render(<PulseErrorState title="Could not load">Try again shortly.</PulseErrorState>)

    expect(screen.getByRole('alert')).toHaveTextContent('Could not load')
    expect(screen.getByRole('alert')).toHaveTextContent('Try again shortly.')
  })

  it('provides reusable Pulse card and button variants', () => {
    render(<PulseCard><PulseButton variant="accent">Save</PulseButton></PulseCard>)
    expect(screen.getByText('Save').closest('section')).toHaveClass('pulse-card')
    expect(screen.getByRole('button', { name: 'Save' })).toHaveClass('pulse-button-accent')
  })
})
