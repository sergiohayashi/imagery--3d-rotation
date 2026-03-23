import styles from "./FullMarkdown.module.css"
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { twilight, vs, oneLight, oneDark, materialLight} from 'react-syntax-highlighter/dist/esm/styles/prism';
import React, {useContext} from 'react';
import ReactMarkdown from 'react-markdown';
import supersub from 'remark-supersub';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import {ThemeContext} from "../../redux/ThemeContext";
import TextWithFormulas from "../TextWithFormulas/TextWithFormulas";
import {setErrorMessage, setInfoMessage} from "../../redux/actions";
import {AppContext} from "../../redux/AppContext";

// ref: https://remarkjs.github.io/react-markdown/

const FullMarkdownOld = ({ text }) => {
    const { theme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);

    if (!text) return null;

    const handleCopyContent = (content) => {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(content).then(() => {
                console.log('Content copied to clipboard');
                dispatch( setInfoMessage('Content copied to clipboard'));

                // Optionally, you can display a message to the user indicating the copy was successful.
            }).catch(err => {
                console.error('Could not copy text: ', err);
            });
        } else {
            setErrorMessage( "Not supported in this browser");
        }
    };

    // const langSubset = [
    //     'python',
    //     'javascript',
    //     'java',
    //     'go',
    //     'bash',
    //     'c',
    //     'cpp',
    //     'csharp',
    //     'css',
    //     'diff',
    //     'graphql',
    //     'json',
    //     'kotlin',
    //     'less',
    //     'lua',
    //     'makefile',
    //     'markdown',
    //     'objectivec',
    //     'perl',
    //     'php',
    //     'php-template',
    //     'plaintext',
    //     'python-repl',
    //     'r',
    //     'ruby',
    //     'rust',
    //     'scss',
    //     'shell',
    //     'sql',
    //     'swift',
    //     'typescript',
    //     'vbnet',
    //     'wasm',
    //     'xml',
    //     'yaml',
    // ];
    // const rehypePlugins = [
    //     [rehypeKatex, { output: 'mathml' }],
    //     [
    //         rehypeHighlight,
    //         {
    //             detect: true,
    //             ignoreMissing: true,
    //             subset: langSubset,
    //         },
    //     ],
    //     [rehypeRaw],
    // ];
    //
    // return (
    //     <ReactMarkdown
    //         remarkPlugins={[supersub, remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
    //         rehypePlugins={rehypePlugins}
    //         // linkTarget="_new"
    //     >
    //         {text}
    //     </ReactMarkdown>
    // );


    const renderers = {
        code({ language, value }) {
            return (
                <SyntaxHighlighter style={theme === 'dark' ? oneDark : oneLight} language={language} children={value} />
            );
        }
    };

    return (
        <ReactMarkdown
            remarkPlugins={[supersub, remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
            rehypePlugins={[
                [rehypeKatex, { output: 'mathml' }],
                [rehypeHighlight, { detect: true, ignoreMissing: true }],
                rehypeRaw
            ]}
            components={renderers}
        >
            {text}
        </ReactMarkdown>
    );
};

export default FullMarkdownOld;
