"use client";

import React, { useState, useEffect, useCallback } from 'react';
import {
  StreamVideo,
  StreamVideoClient,
  Call,
  StreamCall,
  SpeakerLayout,
  CallControls,
  useCallStateHooks,
} from '@stream-io/video-react-sdk';
import { Loader2, Mic, Video, Users, Play, StopCircle } from 'lucide-react';
import '@stream-io/video-react-sdk/dist/css/styles.css';

const API_KEY = process.env.NEXT_PUBLIC_STREAM_API_KEY || ""; // Should be fetched from backend or env

export default function CallInterface() {
  const [client, setClient] = useState<StreamVideoClient | null>(null);
  const [call, setCall] = useState<Call | null>(null);
  const [callId, setCallId] = useState("");
  const [userId, setUserId] = useState(`user-${Math.floor(Math.random() * 1000)}`);
  const [isJoining, setIsJoining] = useState(false);
  const [agentStatus, setAgentStatus] = useState<string | null>(null);
  const [isSpawningAgent, setIsSpawningAgent] = useState(false);

  const joinCall = async () => {
    if (!callId) return;
    setIsJoining(true);
    
    try {
      // 1. Get token from our Vercel API
      const response = await fetch(`/api/token?user_id=${userId}`, { method: 'POST' });
      const { token, api_key } = await response.json();
      
      // 2. Init Stream Client
      const user = { id: userId, name: userId };
      const streamClient = new StreamVideoClient({ apiKey: api_key || API_KEY, user, token });
      setClient(streamClient);
      
      // 3. Init Call
      const streamCall = streamClient.call('default', callId);
      await streamCall.join({ create: true });
      setCall(streamCall);
    } catch (err) {
      console.error("Failed to join call:", err);
      alert("Failed to join call. Check your Stream credentials in .env");
    } finally {
      setIsJoining(false);
    }
  };

  const spawnAgent = async () => {
    if (!call) return;
    setIsSpawningAgent(true);
    setAgentStatus("Requesting agent...");
    
    try {
      const response = await fetch('/api/start-agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ call_id: call.id, call_type: 'default' }),
      });
      
      if (!response.body) return;
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              setAgentStatus(data.status);
              if (data.status === 'error') {
                alert(`Agent Error: ${data.message}`);
              }
            } catch (e) {
              // Ignore parse errors for heartbeats
            }
          }
        }
      }
    } catch (err) {
      console.error("Agent spawn failed:", err);
    } finally {
      setIsSpawningAgent(false);
    }
  };

  if (!call) {
    return (
      <div className="flex flex-col gap-6 max-w-md mx-auto py-12">
        <div className="space-y-2">
          <label className="text-sm text-gray-400">Your User ID</label>
          <input 
            type="text" 
            value={userId} 
            onChange={(e) => setUserId(e.target.value)}
            className="w-full bg-[#1a1a1a] border border-gray-800 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm text-gray-400">Call ID (e.g. demo-123)</label>
          <input 
            type="text" 
            placeholder="Enter call ID..." 
            value={callId} 
            onChange={(e) => setCallId(e.target.value)}
            className="w-full bg-[#1a1a1a] border border-gray-800 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button 
          onClick={joinCall}
          disabled={!callId || isJoining}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-800 disabled:text-gray-500 rounded-lg p-3 font-bold transition-all flex items-center justify-center gap-2"
        >
          {isJoining ? <Loader2 className="animate-spin" /> : <Play size={18} />}
          Join Call
        </button>
      </div>
    );
  }

  return (
    <StreamVideo client={client!}>
      <StreamCall call={call}>
        <div className="flex flex-col gap-4">
          <div className="flex justify-between items-center px-2">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-xs text-gray-400 uppercase tracking-widest font-bold">Live: {callId}</span>
            </div>
            <div className="flex items-center gap-4">
               {agentStatus && (
                 <span className="text-xs bg-blue-900/30 text-blue-400 px-3 py-1 rounded-full border border-blue-800/50">
                   Agent: {agentStatus}
                 </span>
               )}
               <button 
                onClick={spawnAgent}
                disabled={isSpawningAgent}
                className="text-xs bg-purple-600 hover:bg-purple-700 disabled:bg-gray-800 px-4 py-1.5 rounded-lg font-bold flex items-center gap-2 transition-all"
              >
                {isSpawningAgent ? <Loader2 size={14} className="animate-spin" /> : <Users size={14} />}
                Spawn Agent
              </button>
            </div>
          </div>
          
          <div className="aspect-video bg-black rounded-xl overflow-hidden border border-gray-800">
            <SpeakerLayout />
          </div>
          
          <div className="flex justify-center">
            <CallControls onLeave={() => window.location.reload()} />
          </div>
        </div>
      </StreamCall>
    </StreamVideo>
  );
}
