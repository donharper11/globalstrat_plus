import React from 'react';
import { Alert } from 'antd';

const WarningBanner = ({ message, type = 'warning', closable = true, style }) => {
  if (!message) return null;
  return (
    <Alert
      message={message}
      type={type}
      showIcon
      closable={closable}
      style={{ marginBottom: 12, ...style }}
    />
  );
};

export default WarningBanner;
