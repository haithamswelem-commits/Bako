import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import Modal from './Modal'

describe('Modal', () => {
  it('closes with Escape and exposes its title accessibly', () => {
    const onClose = vi.fn()
    render(
      <Modal isOpen onClose={onClose} title="Settings">
        <p>Profile options</p>
      </Modal>,
    )

    expect(screen.getByRole('dialog', { name: 'Settings' })).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })
})
