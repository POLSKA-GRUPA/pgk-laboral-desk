import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { chatAPI } from '../services/api';
import type { ChatMessage } from '../types';

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg: ChatMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setSending(true);

    try {
      const res = await chatAPI.send({ message: input });
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.data.response || 'Sin respuesta' },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Error al procesar la consulta.' },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="chat-container">
      <h2>Chat Laboral</h2>
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble chat-bubble-${msg.role}`}>
            {msg.content}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <Space.Compact style={{ width: '100%' }}>
        <Input
          size="large"
          placeholder="Describe tu consulta laboral..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={handleSend}
          disabled={sending}
        />
        <Button type="primary" size="large" icon={<SendOutlined />} onClick={handleSend} loading={sending}>
          Enviar
        </Button>
      </Space.Compact>
    </div>
  );
}
