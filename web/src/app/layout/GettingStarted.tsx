import { Icon } from '../../shared/ui/Icon'

const steps = [
  'Connect app stores',
  'Setup server notifications',
  'Install Adapty SDK',
  'Create product',
  'Create flow or paywall',
  'Create placement',
  'Make test purchase',
]

export function GettingStarted() {
  return (
    <section className="getting-started" aria-labelledby="getting-started-title">
      <h2 id="getting-started-title">Getting started <Icon name="chevron-down" size={15} /></h2>
      <div className="getting-started-progress" aria-hidden="true" />
      <ul>
        {steps.map((step) => <li key={step}>{step}</li>)}
      </ul>
    </section>
  )
}
