export default function Landing({ onStart }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary via-secondary to-primary flex items-center justify-center p-4">
      <div className="max-w-2xl text-center">
        <h1 className="text-5xl font-bold mb-4">Portfolio AI</h1>
        <p className="text-xl text-gray-300 mb-6">
          Chat with an AI trained on 26 years of enterprise infrastructure expertise
        </p>

        <div className="bg-secondary p-8 rounded-lg mb-8 text-left">
          <h2 className="text-2xl font-semibold mb-4">About Chris Wetzel</h2>
          <ul className="space-y-2 text-gray-300">
            <li>✓ 26 years in IT infrastructure & systems</li>
            <li>✓ Senior infrastructure engineer (9.5 years MSP experience)</li>
            <li>✓ Expertise: cloud migration, SOC2 compliance, disaster recovery</li>
            <li>✓ Projects: 50→300 user global infrastructure, $1.5M+ risk prevented</li>
          </ul>
        </div>

        <button
          onClick={onStart}
          className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition"
        >
          Start Chat
        </button>

        <p className="text-sm text-gray-400 mt-8">
          Ask about infrastructure, cloud, compliance, disaster recovery, or anything from my experience
        </p>
      </div>
    </div>
  )
}
