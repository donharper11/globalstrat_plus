import React from 'react';

function InputField({ label, value, onChange, prefix = '', suffix = '', type = 'number', disabled = false, helper = '', min, max, step, style }) {
  return (
    <div className={`ds-input-field ${disabled ? 'disabled' : ''}`} style={style}>
      {label && <label className="ds-input-label">{label}</label>}
      <div className="ds-input-wrapper">
        {prefix && <span className="ds-input-prefix">{prefix}</span>}
        <input
          type={type}
          value={value}
          onChange={onChange}
          disabled={disabled}
          className="ds-input-control"
          min={min}
          max={max}
          step={step}
        />
        {suffix && <span className="ds-input-suffix">{suffix}</span>}
      </div>
      {helper && <span className="ds-input-helper">{helper}</span>}
    </div>
  );
}

export default InputField;
