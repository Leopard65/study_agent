export default function ExamPractice() {
  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">真题练习</h1>
      <div className="bg-white rounded-xl shadow p-10 text-center">
        <div className="text-5xl mb-4">📋</div>
        <h2 className="text-xl font-semibold text-gray-700 mb-2">功能开发中</h2>
        <p className="text-gray-400 text-sm mb-6">
          真题练习模块即将上线，敬请期待
        </p>
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg text-sm text-gray-500">
          <span className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></span>
          计划支持：历年真题、模拟考试、限时训练
        </div>
      </div>
    </div>
  );
}
