'use client';

import { useEffect, useRef } from 'react';
import Editor from '@monaco-editor/react';

interface CodeEditorProps {
  value: string;
  onChange: (value: string | undefined) => void;
  language: 'python' | 'java' | 'cpp';
  readOnly?: boolean;
  height?: string;
}

export default function CodeEditor({
  value,
  onChange,
  language,
  readOnly = false,
  height = '400px',
}: CodeEditorProps) {
  const editorRef = useRef<any>(null);

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;
    
    // Configure editor options
    editor.updateOptions({
      fontSize: 14,
      tabSize: 2,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      automaticLayout: true,
      wordWrap: 'on',
      lineNumbers: 'on',
      roundedSelection: false,
      cursorStyle: 'line',
      readOnly: readOnly,
    });
  };

  // Map language to Monaco language ID
  const getLanguageId = (lang: string): string => {
    switch (lang) {
      case 'python':
        return 'python';
      case 'java':
        return 'java';
      case 'cpp':
        return 'cpp';
      default:
        return 'plaintext';
    }
  };

  // Get theme based on system preference
  const getTheme = (): string => {
    if (typeof window !== 'undefined') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'vs-dark' : 'light';
    }
    return 'light';
  };

  return (
    <div className="w-full border border-zinc-300 dark:border-zinc-600 rounded-md overflow-hidden">
      <Editor
        height={height}
        language={getLanguageId(language)}
        value={value}
        onChange={onChange}
        onMount={handleEditorDidMount}
        theme={getTheme()}
        options={{
          readOnly: readOnly,
          fontSize: 14,
          tabSize: 2,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          wordWrap: 'on',
          lineNumbers: 'on',
          roundedSelection: false,
          cursorStyle: 'line',
          fontFamily: "'Fira Code', 'Courier New', monospace",
        }}
      />
    </div>
  );
}
