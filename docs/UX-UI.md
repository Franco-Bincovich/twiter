# UX/UI — Agencia

> Documento de referencia para el diseño y desarrollo de interfaces de todos los productos.
> Los usuarios de nuestros productos son pymes y empresas con bajo conocimiento técnico.
> Cada decisión de diseño tiene que estar al servicio de que cualquier persona
> pueda usar el producto sin necesitar ayuda externa.
> Stack: React · Next.js · Tailwind CSS · Shadcn/ui

---

## Principios generales

**Claridad sobre creatividad** — una interfaz que sorprende pero confunde es un mal diseño.
Cada elemento en pantalla tiene que tener un propósito claro y comunicarlo sin ambigüedad.

**El usuario nunca debería preguntarse qué hacer** — si alguien tiene que pensar más de
dos segundos para entender su próximo paso, la interfaz falló.

**Consistencia genera confianza** — los usuarios de pymes con bajo conocimiento técnico
confían más en un producto cuando todo se comporta de la misma manera.
Un botón primario siempre se ve igual. Un error siempre aparece en el mismo lugar.

**Responsive no es opcional** — el producto tiene que verse impecable en cualquier
dispositivo. No "funcionar en mobile" — verse y usarse impecable.

---

## 1. Stack de UI recomendado

### Tailwind CSS + Shadcn/ui

Para el stack de la agencia (React + Next.js), la combinación recomendada es:

- **Tailwind CSS** — utilidades de estilo, espaciado, tipografía y responsive
- **Shadcn/ui** — biblioteca de componentes accesibles y personalizables

Shadcn/ui no es una dependencia instalada — los componentes se copian al proyecto
y se modifican libremente. Esto significa control total sobre el código y sin
actualizaciones que rompan el diseño.

```bash
# Instalación inicial en cada proyecto frontend
npx create-next-app@latest [proyecto] --typescript --tailwind
npx shadcn-ui@latest init

# Agregar componentes según se necesiten
npx shadcn-ui@latest add button
npx shadcn-ui@latest add input
npx shadcn-ui@latest add dialog
npx shadcn-ui@latest add table
```

### Por qué esta combinación

- Los componentes de Shadcn/ui son accesibles por defecto (ARIA, teclado, foco)
- Tailwind hace que el responsive sea sistemático, no un parche
- Los dos se adaptan al manual de marca de cada producto sin reescribir desde cero
- Claude Code y Claude Design conocen muy bien este stack — el código generado es confiable

---

## 2. Design system por producto

Cada producto tiene su propio design system definido en un archivo central.
Cuando Claude Design genera componentes, este archivo es el contexto obligatorio.

### Estructura del design system

```typescript
// styles/design-system.ts — único archivo de tokens de diseño por producto

export const designSystem = {
  // Colores — definidos desde el manual de marca del producto
  colors: {
    primary: "#[color-principal]",
    primaryHover: "#[color-principal-hover]",
    secondary: "#[color-secundario]",
    background: "#[fondo]",
    surface: "#[superficie-de-cards]",
    border: "#[bordes]",
    text: {
      primary: "#[texto-principal]",
      secondary: "#[texto-secundario]",
      disabled: "#[texto-deshabilitado]",
    },
    status: {
      success: "#22c55e",
      warning: "#f59e0b",
      error: "#ef4444",
      info: "#3b82f6",
    }
  },

  // Tipografía
  typography: {
    fontFamily: "[fuente-del-producto]",
    sizes: {
      xs: "0.75rem",    // 12px — labels, captions
      sm: "0.875rem",   // 14px — texto secundario
      base: "1rem",     // 16px — texto de cuerpo
      lg: "1.125rem",   // 18px — subtítulos
      xl: "1.25rem",    // 20px — títulos de sección
      "2xl": "1.5rem",  // 24px — títulos de página
      "3xl": "1.875rem" // 30px — headings principales
    }
  },

  // Espaciado — basado en múltiplos de 4px
  spacing: {
    xs: "4px",
    sm: "8px",
    md: "16px",
    lg: "24px",
    xl: "32px",
    "2xl": "48px",
    "3xl": "64px"
  },

  // Bordes y sombras
  borderRadius: {
    sm: "4px",
    md: "8px",
    lg: "12px",
    full: "9999px"
  }
}
```

### Cómo aplicar el design system en Tailwind

```javascript
// tailwind.config.ts — extender Tailwind con los tokens del producto
import { designSystem } from './styles/design-system'

export default {
  theme: {
    extend: {
      colors: {
        primary: designSystem.colors.primary,
        secondary: designSystem.colors.secondary,
        // ...
      },
      fontFamily: {
        sans: [designSystem.typography.fontFamily, 'sans-serif'],
      }
    }
  }
}
```

---

## 3. Componentes base

Estos componentes tienen que existir en todo proyecto desde el día 1.
Son los bloques con los que se construye el 80% de cualquier interfaz.

### Button — los tres estados obligatorios

```tsx
// components/ui/Button.tsx

// Variantes
type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive"
type ButtonSize = "sm" | "md" | "lg"

// Estado de carga — siempre implementado
<Button loading={isSubmitting}>
  {isSubmitting ? "Guardando..." : "Guardar cambios"}
</Button>

// Estado deshabilitado — siempre con razón visible
<Button disabled={!isFormValid} title="Completá todos los campos obligatorios">
  Continuar
</Button>
```

### Input — estados visuales claros

```tsx
// Un input siempre comunica su estado visualmente
<Input
  label="Email"
  placeholder="nombre@empresa.com"
  error="El email no tiene un formato válido"   // estado de error
  success="Email verificado"                    // estado de éxito
  helper="Este email se usará para iniciar sesión" // texto de ayuda
/>
```

### Estados de carga, vacío y error — siempre implementados

```tsx
// Cada componente que carga datos implementa los tres estados

// Estado de carga
if (isLoading) return <ContactListSkeleton />

// Estado vacío — con mensaje explicativo y acción
if (contacts.length === 0) return (
  <EmptyState
    icon={<UsersIcon />}
    title="Todavía no tenés contactos"
    description="Agregá tu primer contacto para empezar a usar el sistema."
    action={<Button onClick={openCreateModal}>Agregar contacto</Button>}
  />
)

// Estado de error — con opción de reintentar
if (error) return (
  <ErrorState
    title="No pudimos cargar tus contactos"
    description="Hubo un problema al conectar con el servidor."
    action={<Button variant="secondary" onClick={refetch}>Reintentar</Button>}
  />
)

// Estado con datos
return <ContactList contacts={contacts} />
```

---

## 4. Responsive — reglas de implementación

### Mobile-first siempre

El diseño se construye primero para mobile y se expande para pantallas más grandes.
En Tailwind esto significa escribir los estilos base para mobile y usar prefijos
para pantallas más grandes.

```tsx
// ✅ Mobile-first — base para mobile, sm/md/lg para más grande
<div className="
  flex flex-col gap-4        // mobile: columna
  md:flex-row md:gap-6       // tablet: fila
  lg:gap-8                   // desktop: más espacio
">

// ❌ Desktop-first — más difícil de mantener y propenso a bugs en mobile
<div className="
  flex flex-row gap-8
  sm:flex-col sm:gap-4
">
```

### Breakpoints estándar

| Nombre | Ancho mínimo | Dispositivo típico |
|---|---|---|
| base | 0px | Mobile portrait |
| sm | 640px | Mobile landscape / tablet pequeña |
| md | 768px | Tablet |
| lg | 1024px | Desktop pequeño |
| xl | 1280px | Desktop |
| 2xl | 1536px | Desktop grande |

### Reglas de responsive por elemento

```tsx
// Tipografía — escala según pantalla
<h1 className="text-xl md:text-2xl lg:text-3xl font-bold">
  Título de página
</h1>

// Grillas — de 1 columna en mobile a múltiples en desktop
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

// Navegación — hamburger en mobile, sidebar en desktop
<nav className="hidden lg:flex">        // desktop
<button className="lg:hidden">          // mobile

// Tablas — scroll horizontal en mobile
<div className="overflow-x-auto">
  <table className="min-w-full">
```

### Touch targets — el error más común en mobile

Los elementos interactivos en mobile tienen que tener un área táctil mínima de 44x44px.
Un botón o link más pequeño es frustrante de tocar en un teléfono.

```tsx
// ✅ Touch target correcto
<button className="min-h-[44px] min-w-[44px] px-4 py-3">
  Guardar
</button>

// ❌ Demasiado pequeño para tocar con precisión en mobile
<button className="px-2 py-1 text-xs">
  Guardar
</button>
```

---

## 5. UX para usuarios con bajo conocimiento técnico

### 5.1 Lenguaje claro y sin jerga técnica

Los mensajes de la interfaz se escriben como si se los explicaras a alguien
que nunca usó software de gestión.

```
# ✅ Lenguaje claro
"Guardando tus cambios..."
"¡Listo! Tu cuenta está activada."
"Algo salió mal. Intentá de nuevo en unos minutos."
"No tenés contactos todavía. ¡Agregá el primero!"

# ❌ Lenguaje técnico
"Procesando request..."
"200 OK — Operación completada exitosamente"
"Error 500: Internal Server Error"
"No se encontraron registros en la base de datos"
```

### 5.2 Feedback inmediato en cada acción

El usuario siempre sabe qué está pasando después de hacer algo.

| Acción del usuario | Feedback inmediato |
|---|---|
| Hace click en "Guardar" | El botón muestra spinner + "Guardando..." |
| El guardado fue exitoso | Toast verde: "Cambios guardados" |
| El guardado falló | Toast rojo: "No se pudo guardar. Intentá de nuevo." |
| Borra algo | Confirmación: "¿Seguro que querés eliminar esto?" |
| Sube un archivo | Barra de progreso visible |

```tsx
// Toast notifications — siempre con contexto claro
toast.success("Contacto guardado correctamente")
toast.error("No se pudo guardar el contacto. Verificá tu conexión.")
toast.warning("Tu plan vence en 3 días")
toast.info("Tus datos se sincronizaron automáticamente")
```

### 5.3 Formularios — las reglas más importantes

Los formularios son el punto de mayor fricción para usuarios no técnicos.

```tsx
// ✅ Reglas de formularios

// 1. Labels siempre visibles — nunca solo placeholder
<Input label="Nombre de la empresa" placeholder="Ej: Acme S.A." />

// 2. Validación en tiempo real — no esperar al submit
<Input
  label="Email"
  onChange={validateEmail}
  error={emailError}          // aparece mientras escribe si hay error
/>

// 3. Errores específicos y accionables
error="El email debe tener el formato nombre@empresa.com"  // ✅
error="Email inválido"                                      // ❌ muy genérico

// 4. Campos obligatorios marcados con asterisco y nota al pie
<label>Nombre de la empresa <span className="text-red-500">*</span></label>
<p className="text-sm text-gray-500">Los campos con * son obligatorios</p>

// 5. El botón de submit siempre describe la acción
<Button>Crear cuenta</Button>   // ✅
<Button>Enviar</Button>         // ❌ muy genérico
<Button>OK</Button>             // ❌ no dice nada
```

### 5.4 Confirmaciones antes de acciones destructivas

Antes de eliminar algo o hacer una acción irreversible, siempre pedir confirmación
con un modal que explica exactamente qué va a pasar.

```tsx
// Modal de confirmación para acciones destructivas
<ConfirmDialog
  title="Eliminar contacto"
  description="Vas a eliminar a Juan Pérez de tus contactos. Esta acción no se puede deshacer."
  confirmLabel="Sí, eliminar"
  confirmVariant="destructive"
  cancelLabel="Cancelar"
  onConfirm={handleDelete}
/>
```

---

## 6. Flujos simples — dashboards, tablas y acciones directas

Para productos con interfaces de consulta y acción directa.

### Estructura de página estándar

```tsx
// Layout de página de dashboard — estructura consistente en todos los productos
<PageLayout>
  {/* Header con título y acción principal */}
  <PageHeader
    title="Contactos"
    description="Gestioná todos tus contactos desde acá"
    action={
      <Button onClick={openCreateModal}>
        + Agregar contacto
      </Button>
    }
  />

  {/* Filtros y búsqueda */}
  <FiltersBar>
    <SearchInput placeholder="Buscar por nombre o empresa..." />
    <FilterSelect label="Industria" options={industryOptions} />
  </FiltersBar>

  {/* Contenido principal */}
  <DataTable
    data={contacts}
    columns={contactColumns}
    isLoading={isLoading}
    emptyState={<ContactsEmptyState />}
  />
</PageLayout>
```

### Tablas de datos — reglas

```tsx
// ✅ Reglas para tablas de datos

// 1. Siempre con estado de carga (skeleton), vacío y error
// 2. Columnas con ancho definido para evitar saltos al cargar
// 3. Acciones por fila en el último column — solo las más usadas
<TableCell>
  <DropdownMenu>
    <DropdownMenuItem onClick={() => handleEdit(row)}>Editar</DropdownMenuItem>
    <DropdownMenuItem onClick={() => handleDelete(row)} className="text-red-600">
      Eliminar
    </DropdownMenuItem>
  </DropdownMenu>
</TableCell>

// 4. Paginación siempre visible cuando hay más de 20 registros
// 5. En mobile: scroll horizontal o vista de cards en lugar de tabla
```

---

## 7. Flujos complejos — wizards y onboarding guiado

Para productos con flujos de varios pasos (onboarding, configuración inicial, formularios largos).

### Estructura de wizard

```tsx
// Un wizard tiene: progreso visible, navegación clara y resumen al final

<WizardLayout>
  {/* Indicador de progreso — siempre visible */}
  <StepIndicator
    steps={["Tu empresa", "Tu plan", "Configuración", "Listo"]}
    currentStep={currentStep}
  />

  {/* Contenido del paso actual */}
  <WizardStep title="Contanos sobre tu empresa">
    {/* Solo los campos necesarios para este paso */}
    {/* Un paso = una decisión o un conjunto de datos relacionados */}
  </WizardStep>

  {/* Navegación — siempre en el mismo lugar */}
  <WizardNavigation
    onBack={currentStep > 0 ? handleBack : undefined}
    onNext={handleNext}
    nextLabel={isLastStep ? "Finalizar configuración" : "Continuar"}
    isLoading={isSubmitting}
  />
</WizardLayout>
```

### Reglas para wizards

```
1. Máximo 5 pasos — más de 5 pasos y el usuario abandona
2. Cada paso tiene un título que explica qué se está configurando
3. El progreso siempre es visible — el usuario sabe dónde está y cuánto falta
4. Los datos se guardan automáticamente entre pasos — si cierra y vuelve, retoma donde estaba
5. El último paso es siempre un resumen de lo configurado antes de confirmar
6. Si un paso es opcional, marcarlo claramente como opcional
```

### Onboarding in-app

El onboarding es la primera experiencia del usuario con el producto.
Define si van a seguir usándolo o lo van a abandonar.

```tsx
// Checklist de onboarding — guía al usuario sin abrumarlo
<OnboardingChecklist
  title="Empezá a usar [Producto]"
  description="Completá estos pasos para sacarle el máximo provecho"
  steps={[
    {
      id: "profile",
      title: "Completá tu perfil",
      description: "Agregá el nombre de tu empresa y logo",
      completed: user.profileCompleted,
      action: <Button size="sm" onClick={goToProfile}>Completar</Button>
    },
    {
      id: "first_contact",
      title: "Agregá tu primer contacto",
      description: "Importá desde Excel o agregalo manualmente",
      completed: hasContacts,
      action: <Button size="sm" onClick={openAddContact}>Agregar</Button>
    },
    // ...
  ]}
/>
```

---

## 8. Guía de UX contextual — tooltips y mensajes de ayuda

Para usuarios con bajo conocimiento técnico, la interfaz tiene que anticipar
las dudas y responderlas sin que tengan que salir a buscar ayuda.

### Cuándo usar cada elemento

| Elemento | Cuándo usarlo | Cuándo no usarlo |
|---|---|---|
| **Tooltip** | Explicar un icono o término técnico | No para información crítica |
| **Helper text** | Explicar el formato esperado de un campo | No repetir el label |
| **Inline info** | Contexto importante antes de una acción | No para texto muy largo |
| **Modal de ayuda** | Explicaciones largas o tutoriales | No para confirmaciones simples |
| **Empty state** | Primera vez que el usuario llega a una sección | No solo para llenar espacio |

### Ejemplos de implementación

```tsx
// Tooltip para términos que pueden no conocer
<label className="flex items-center gap-1">
  Nivel de confianza
  <Tooltip content="Porcentaje que indica qué tan seguro está el sistema de que este contacto es correcto">
    <InfoIcon className="w-4 h-4 text-gray-400" />
  </Tooltip>
</label>

// Helper text para formato de campos
<Input
  label="Teléfono"
  placeholder="11 2345-6789"
  helper="Incluí el código de área sin el 0"
/>

// Empty state explicativo con acción clara
<EmptyState
  icon={<FileIcon />}
  title="No hay reportes generados todavía"
  description="Los reportes se generan automáticamente cada lunes.
               También podés generar uno manualmente cuando quieras."
  action={<Button onClick={generateReport}>Generar reporte ahora</Button>}
/>
```

---

## 9. Navegación — reglas generales

### Estructura de navegación por tipo de producto

```tsx
// Sidebar — para productos con múltiples secciones (SaaS con dashboard)
<Sidebar>
  <SidebarLogo />
  <SidebarNav>
    <NavItem href="/dashboard" icon={<HomeIcon />} label="Inicio" />
    <NavItem href="/contacts" icon={<UsersIcon />} label="Contactos" />
    <NavItem href="/reports" icon={<ChartIcon />} label="Reportes" />
  </SidebarNav>
  <SidebarFooter>
    <NavItem href="/settings" icon={<SettingsIcon />} label="Configuración" />
    <UserMenu />
  </SidebarFooter>
</Sidebar>

// Topbar — para productos simples o microsistemas
<Topbar>
  <Logo />
  <TopbarNav>
    <NavItem href="/dashboard">Inicio</NavItem>
    <NavItem href="/contacts">Contactos</NavItem>
  </TopbarNav>
  <UserMenu />
</Topbar>
```

### Reglas de navegación

```
1. El item activo siempre está visualmente destacado
2. La ruta actual visible en el breadcrumb cuando hay más de 2 niveles de profundidad
3. En mobile el sidebar se convierte en menú hamburger o bottom navigation
4. No más de 7 items en la navegación principal — si hay más, agrupar
5. Las acciones destructivas (cerrar sesión, eliminar cuenta) siempre al final y separadas
```

---

## 10. Accesibilidad mínima obligatoria

Accesibilidad no es solo para usuarios con discapacidad — mejora la experiencia de todos
y es un requisito para que los productos sean profesionales.

### Reglas básicas no negociables

```tsx
// 1. Imágenes siempre con alt descriptivo
<img src={logo} alt="Logo de Acme S.A." />
<img src={decorative} alt="" />  // decorativas con alt vacío

// 2. Botones con texto descriptivo o aria-label
<Button>Guardar cambios</Button>                                    // ✅
<Button aria-label="Eliminar contacto Juan Pérez"><TrashIcon /></Button>  // ✅
<Button><TrashIcon /></Button>                                      // ❌ sin contexto

// 3. Formularios con labels asociados
<label htmlFor="email">Email</label>
<input id="email" type="email" />

// 4. Contraste de color mínimo 4.5:1 para texto normal
// Shadcn/ui cumple esto por defecto — no modificar colores de texto sin verificar contraste

// 5. Foco visible — nunca outline: none sin reemplazo
// Tailwind tiene focus-visible:ring que mantiene el foco visible para teclado
<button className="focus-visible:ring-2 focus-visible:ring-primary">
```

---

## 11. Cómo trabajar con Claude Design

Claude Design genera componentes visuales basándose en el contexto que le dás.
Sin contexto, genera algo genérico que no encaja con el producto.

### Estructura del prompt para Claude Design

```
Contexto del producto:
- Nombre: [nombre]
- Usuarios: pymes con bajo conocimiento técnico
- Stack: React + Next.js + Tailwind + Shadcn/ui

Design system:
- Color primario: [hex]
- Color secundario: [hex]
- Fondo: [hex]
- Tipografía: [fuente]
- Border radius: [valor]

Qué necesito:
[Descripción específica del componente o pantalla]

Estados que tiene que contemplar:
- Estado normal
- Estado de carga
- Estado vacío (si aplica)
- Estado de error (si aplica)

Responsive:
- Mobile: [descripción del comportamiento en mobile]
- Desktop: [descripción del comportamiento en desktop]
```

### Ejemplo real

```
Contexto del producto:
- Plataforma de gestión de contactos para pymes
- Usuarios no técnicos que necesitan interfaces simples

Design system:
- Color primario: #6366f1 (indigo)
- Fondo: #f9fafb
- Superficie de cards: #ffffff
- Tipografía: Inter
- Border radius: 8px

Qué necesito:
Componente de tabla de contactos con columnas: Nombre, Empresa, Email, Estado.
Cada fila tiene un menú de acciones (editar, eliminar).

Estados:
- Cargando: skeleton de 5 filas
- Vacío: mensaje "Todavía no tenés contactos" con botón "Agregar primero"
- Con datos: tabla completa con paginación de 20 por página

Responsive:
- Mobile: cards en lugar de tabla, una por contacto
- Desktop: tabla completa
```

---

## Checklist de UX/UI — antes de cada deploy

```
[ ] Todos los estados implementados: carga, vacío, error, con datos
[ ] Responsive verificado en mobile (375px), tablet (768px) y desktop (1280px)
[ ] Los textos de la interfaz no tienen jerga técnica ni mensajes de error crudos
[ ] Los formularios tienen labels visibles, validación en tiempo real y errores específicos
[ ] Las acciones destructivas tienen modal de confirmación
[ ] Los botones describen la acción (no "Enviar", no "OK")
[ ] Los touch targets tienen mínimo 44x44px en mobile
[ ] Los íconos sin texto tienen aria-label o tooltip
[ ] El contraste de colores es legible (mínimo 4.5:1 para texto)
[ ] El item activo en la navegación está visualmente destacado
[ ] Los flujos de wizard guardan progreso automáticamente
[ ] Los toasts de feedback aparecen después de cada acción importante
```

---

*Agencia · Documento interno de desarrollo · 2026*
*Versión 1.0 — Stack: React · Next.js · Tailwind CSS · Shadcn/ui*
