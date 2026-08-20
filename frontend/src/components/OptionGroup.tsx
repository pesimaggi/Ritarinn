/**
 * A labelled row of mutually exclusive options.
 *
 * Rendered as radio inputs rather than a <select> so every choice is visible
 * without interaction — there are only a handful, and the labels themselves
 * explain what the feature can do.
 */

export interface OptionGroupProps<T extends string> {
  label: string;
  name: string;
  value: T;
  options: readonly { readonly value: T; readonly label: string }[];
  onChange: (value: T) => void;
  disabled?: boolean;
}

export function OptionGroup<T extends string>({
  label,
  name,
  value,
  options,
  onChange,
  disabled,
}: OptionGroupProps<T>) {
  return (
    <fieldset className="ritarinn-options" disabled={disabled}>
      <legend className="ritarinn-options__legend">{label}</legend>
      <div className="ritarinn-options__choices">
        {options.map((option) => (
          <label
            key={option.value}
            className={`ritarinn-chip${option.value === value ? " is-selected" : ""}`}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
