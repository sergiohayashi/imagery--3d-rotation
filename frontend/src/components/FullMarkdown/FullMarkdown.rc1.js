// src/FullMarkdown.js
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import 'highlight.js/styles/github.css';
import remarkMath from "remark-math";
import supersub from "remark-supersub";
import rehypeRaw from "rehype-raw";
import rehypeReact from "rehype-react";

const markdownContent = `
# Hello, React!

This is a sample markdown content.

## Features

- **Bold Text**
- *Italic Text*
- [Link](https://reactjs.org)

## Code Example

\`\`\`javascript
const greeting = "Hello, World!";
console.log(greeting);
\`\`\`

## LaTeX Example

Here is a simple LaTeX formula:

$$
E = mc^2
$$
`;
const preprocessContent = (content) => {
    content = content.replace(/\\\[/g, '$$').replace(/\\\]/g, '$$');
    content = content.replace(/\\\(/g, '$').replace(/\\\)/g, '$');
    return content;
};

const FullMarkdown = ({ content }) => {

    // console.log( 'content', content);

    // const renderers = {
    //     listItem: ({ children }) => <li style={{ marginBottom: 0 }}>{children}</li>,
    // };

    return (
        <ReactMarkdown
            children={preprocessContent(content)}
            remarkPlugins={[supersub, remarkGfm, remarkMath]}
            rehypePlugins={[rehypeRaw, rehypeKatex, rehypeHighlight,
                // [rehypeReact, { createElement: React.createElement, components: renderers }]

            ]}
        />
    );
};

export default FullMarkdown;
