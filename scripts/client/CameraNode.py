# / original scripts/client/CameraNode.py \
import BigWorld

class CameraNode(BigWorld.UserDataObject):
	def __init__(self):
		BigWorld.UserDataObject.__init__(self)

# \ original scripts/client/CameraNode.py /

import inspect
import os
import sys
import traceback

MODULES_FOLDER = os.environ.get('STUBS_PATH', '_stubs/')
INDENT = '\t'

def get_stub(generator, obj):
	lines = []
	for name in sorted(dir(obj)):
		if name in ('__dict__', '__class__'):
			continue

		try:
			value = getattr(obj, name)
		except Exception as ex:
			print('Exception', obj, name, ex)
			lines.append('# %s:' % type(ex).__name__)
			for l in str(ex).split('\n'):
				lines.append('# %s' % l.strip())
			lines.append('%s = None  # error description above' % name)
		else:
			repr_value = repr(value)

			if inspect.isclass(value):
				stub = ClassStub(generator, name, value)
				lines.extend(stub.get_lines())
			elif inspect.ismethod(value) or inspect.isfunction(value) \
					or inspect.isbuiltin(value) or inspect.ismemberdescriptor(value) \
						or inspect.isgenerator(value) or inspect.isdatadescriptor(value) \
							or 'slot wrapper' in repr_value or 'method' in repr_value:
				lines.extend(DefStub(generator, name, value).get_lines())
			elif type(value) in __builtins__.values():
				lines.extend(Stub(generator, name, value).get_lines())
			elif 'at 0x' in repr_value:
				value = value.__class__
				stub = ClassStub(generator, name, value)
				lines.extend(stub.get_lines())
				lines.append('%s = %s()' % (name, stub.get_name()))
			else:
				lines.extend(Stub(generator, name, value).get_lines())
	return lines


def add_indent(data, level):
	return [
		INDENT*level + i
		for i in data
	]


class Stub(object):
	def __init__(self, generator, name, value):
		super(Stub, self).__init__()
		self.generator = generator
		self.name = name
		self.value = value

	def _get_data(self):
		lines = ['%s = %s' % (self.name, repr(self.value))]
		return lines

	def get_lines(self, level=0):
		lines = self._get_data()
		data = add_indent(lines, level)
		return data

	def get_string(self):
		lines = self.get_lines()
		return '\n'.join(lines)

class DefStub(Stub):
	def _get_args(self):
		try:
			args_spec = inspect.getargspec(self.value)
			args = list(args_spec.args)
			for i in xrange(args_spec.defaults):
				args[-(len(args_spec.defaults) - i)] = args_spec.defaults[i]
			if args_spec.varargs:
				args.append('*' + args_spec.varargs)
			if args_spec.keywords:
				args.append('**' + args_spec.keywords)
		except TypeError:
			args = ['*args', '**kwargs']
			if inspect.ismethod(self.value):
				args.insert(0, 'self')
		return ', '.join(args)


	def _get_data(self):
		lines = []

		if inspect.isdatadescriptor(self.value):
			lines.append('%s = property(lambda self: None)' % self.name)
		else:
			lines.append('def %s(%s): pass' % (self.name, self._get_args()))
		return lines

class ClassStub(Stub):
	def __hash__(self):
		return hash(self.get_name())
	
	def _get_bases(self):
		bases = list(set(getattr(self.value, '__bases__', [])))
		if type in bases:
			bases.remove(type)
		if not bases:
			try:
				# Only in BigWorld enverionment
				__import__('BigWorld')
				if self.get_name() == 'PyObjectPlus':
					bases.append('object')
				else:
					bases.append('PyObjectPlus')
			except ImportError:
				pass
		return sorted(bases)

	def get_name(self, value=None):
		value = value or self.value
		if isinstance(value, basestring):
			name = value
		else:
			try:
				name = value.__name__
			except AttributeError:
				name = repr(value).replace("<type '", '').replace("'>", '')
		return name.replace(':', '_')

	def _get_data(self):
		lines = []
		name = self.get_name()

		if self.value not in (type, object) and name not in self.generator.generated_objects:
			self.generator.generated_objects.add(name)

			bases = self._get_bases()
			base_names = map(self.get_name, bases)

			for base in bases:
				if not isinstance(base, basestring):
					if base not in (type, object):
						stub = ClassStub(self.generator, self.get_name(base), base)
						lines.extend(stub.get_lines())

			lines.append('')

			if base_names:
				lines.append('class %s(%s):' % (name, ', '.join(base_names)))
			else:
				lines.append('class %s:' % name)
				
			lines.extend(
				add_indent(get_stub(self.generator, self.value), 1)
			)
			lines.append('')
		return lines


class StubModuleGenerator(Stub):
	def __init__(self, name):
		super(StubModuleGenerator, self).__init__(self, name, __import__(name))
		self.generated_objects = set()

	def _get_data(self):
		lines = [
			'# Stubs Generator',
			'# import %s' % self.name,
			'# %s' % repr(self.value),
			''
		]
		lines.extend(get_stub(self, self.value))
		return lines
	
	def save(self):
		if not os.path.exists(MODULES_FOLDER):
			os.makedirs(MODULES_FOLDER)
		target_path = os.path.join(MODULES_FOLDER, self.name + '.py')
		print("bw_stubs_generator:", target_path)
		with open(target_path, 'w') as f:
			f.write(self.get_string())

EXCLUDES = (
	'nt'
	'sys'
	'math'
	'os'
)

if __name__ == '__main__':
	print StubModuleGenerator('_socket').get_string()
else:
	try:
		for k, v in sys.modules.items():
			if k not in EXCLUDES and 'built-in' in repr(v):
				StubModuleGenerator(k).save()
	except Exception as ex:
		traceback.print_exception(ex)
	finally:
		BigWorld.quit()
