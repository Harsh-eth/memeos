type InputPanelProps = {
  value: string;
  onChange: (v: string) => void;
  onGenerate: () => void;
  disabled?: boolean;
};

export function InputPanel({ value, onChange, onGenerate, disabled }: InputPanelProps) {
  return (
    <div className="ref-input-box">
      <div className="ref-input-row">
        <textarea
          className="ref-textarea"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
          disabled={disabled}
        />
        <button
          type="button"
          className="ref-generate"
          onClick={onGenerate}
          disabled={disabled}
        >
          generate
        </button>
      </div>
      <hr className="ref-input-divider" />
      <p className="ref-helper ref-helper--inbox">
        example: dev sweating over red terminal, make it matrix style.
      </p>
    </div>
  );
}
