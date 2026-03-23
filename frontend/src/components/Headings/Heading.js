import React from 'react';
import styles from './Heading.module.css'

// Title Component
const Title = ({ children }) => {
    return <div className={styles["title"]}>{children}</div>;
};

// Subtitle Component
const Subtitle = ({ children }) => {
    return <div className={styles["sub-title"]}>{children}</div>;
};

// SectionTitle Component
const SectionTitle = ({ children }) => {
    return <div className={styles["section-title"]}>{children}</div>;
};

export { Title, Subtitle, SectionTitle };