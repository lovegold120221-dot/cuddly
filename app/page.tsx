import CallInterface from "@/components/CallInterface";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-8 md:p-24 bg-[#0a0a0a] text-white">
      <div className="z-10 w-full max-w-5xl items-center justify-between font-mono text-sm lg:flex flex-col">
        <h1 className="text-4xl font-bold mb-8 bg-gradient-to-r from-blue-500 to-purple-600 bg-clip-text text-transparent">
          Vision Agents
        </h1>
        <p className="text-gray-400 mb-12 text-center max-w-2xl">
          Real-time AI video coaching and conversation powered by Stream's edge network.
          Deploy your agents to Vercel and talk to them instantly.
        </p>
        
        <div className="w-full bg-[#111] border border-gray-800 rounded-2xl p-6 shadow-2xl">
          <CallInterface />
        </div>
      </div>
      
      <div className="mt-12 text-gray-500 text-xs flex gap-4">
        <span>Powered by Stream Video</span>
        <span>•</span>
        <span>Vision Agents Framework</span>
        <span>•</span>
        <span>Vercel AI</span>
      </div>
    </main>
  );
}
